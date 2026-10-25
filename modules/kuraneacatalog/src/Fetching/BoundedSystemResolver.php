<?php

declare(strict_types=1);

namespace Kuranea\Catalog\Fetching;

/** Bounded NSS A/AAAA resolution for the two supported marketplace hosts. */
final class BoundedSystemResolver implements ResolverInterface
{
    /** @var list<string> */
    private const HOSTS = [
        'www.amazon.co.jp',
        'amazon.co.jp',
        'item.rakuten.co.jp',
    ];

    /** @return list<string> */
    public function resolve(string $host, float $timeoutSeconds): array
    {
        $host = strtolower($host);
        if (!in_array($host, self::HOSTS, true)
            || !is_finite($timeoutSeconds)
            || $timeoutSeconds <= 0
            || !function_exists('proc_open')) {
            throw new FetchException('Marketplace host resolution is unavailable.');
        }

        // The host is selected from a fixed allowlist and passed as an argv
        // element. No shell is involved. Disable AI_ADDRCONFIG so an IPv4-only
        // host cannot hide unsafe AAAA results (or vice versa).
        $pipes = [];
        $path = getenv('PATH');
        $deadline = hrtime(true) / 1e9 + $timeoutSeconds;
        $process = @proc_open(
            ['getent', '--no-addrconfig', 'ahosts', $host],
            [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']],
            $pipes,
            null,
            ['LC_ALL' => 'C', 'PATH' => is_string($path) && $path !== '' ? $path : '/usr/bin:/bin']
        );
        if (!is_resource($process)) {
            throw new FetchException('Marketplace host resolution is unavailable.');
        }

        $stdout = '';
        $outputBytes = 0;
        $exitCode = -1;

        try {
            if (count($pipes) !== 3) {
                throw new FetchException('Marketplace host resolution is unavailable.');
            }
            fclose($pipes[0]);
            if (!stream_set_blocking($pipes[1], false) || !stream_set_blocking($pipes[2], false)) {
                throw new FetchException('Marketplace host resolution is unavailable.');
            }
            while (true) {
                if (hrtime(true) / 1e9 >= $deadline) {
                    throw new FetchException('Marketplace host resolution deadline exceeded.');
                }
                $status = proc_get_status($process);
                if (!is_array($status)) {
                    throw new FetchException('Marketplace host resolution failed.');
                }
                if (!$status['running'] && (int) $status['exitcode'] >= 0) {
                    $exitCode = (int) $status['exitcode'];
                }

                foreach ([1, 2] as $stream) {
                    // At most 8KiB per read, or one byte past the remaining
                    // allowance. Check BEFORE append; stderr is never retained.
                    $chunk = stream_get_contents($pipes[$stream], min(8192, 65536 - $outputBytes + 1));
                    if (!is_string($chunk)) {
                        throw new FetchException('Marketplace host resolution failed.');
                    }
                    if (strlen($chunk) > 65536 - $outputBytes) {
                        throw new FetchException('Marketplace host resolution returned too much data.');
                    }
                    $outputBytes += strlen($chunk);
                    if ($stream === 1) $stdout .= $chunk;
                }

                if (!$status['running'] && feof($pipes[1]) && feof($pipes[2])) {
                    break;
                }
                usleep(10000);
            }
        } catch (\Throwable) {
            throw new FetchException('Marketplace host resolution failed.');
        } finally {
            $status = proc_get_status($process);
            if (is_array($status) && $status['running']) {
                // getent is the direct child, not a shell wrapper. Kill on every
                // failure path and reap it before returning to the caller.
                proc_terminate($process, 9);
            }
            foreach ($pipes as $pipe) {
                if (is_resource($pipe)) fclose($pipe);
            }
            proc_close($process);
        }

        if ($exitCode !== 0 || trim($stdout) === '') {
            throw new FetchException('Marketplace host resolution returned no addresses.');
        }

        $addresses = [];
        foreach (preg_split('/\R/', trim($stdout)) ?: [] as $line) {
            $columns = preg_split('/\s+/', trim($line)) ?: [];
            $address = $columns[0] ?? '';
            if (filter_var($address, FILTER_VALIDATE_IP) === false) {
                throw new FetchException('Marketplace host resolution returned an invalid address set.');
            }
            $addresses[$address] = $address;
        }

        if ($addresses === []) {
            throw new FetchException('Marketplace host resolution returned no addresses.');
        }

        return array_values($addresses);
    }
}
