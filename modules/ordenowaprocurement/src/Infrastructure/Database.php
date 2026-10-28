<?php
declare(strict_types=1);

namespace Ordenowa\Procurement\Infrastructure;

/** One connection for domain writes, locks, audit and the notification outbox. */
final class Database
{
    private object $connection;
    private string $prefix;
    private int $depth = 0;

    public function __construct(object $connection, string $prefix)
    {
        if (!preg_match('/^[A-Za-z0-9_]*$/D', $prefix)) {
            throw new \InvalidArgumentException('Invalid database prefix.', 422);
        }
        $this->connection = $connection;
        $this->prefix = $prefix;
        if ($connection instanceof \PDO) {
            $connection->setAttribute(\PDO::ATTR_ERRMODE, \PDO::ERRMODE_EXCEPTION);
        }
    }

    public function table(string $suffix): string
    {
        if (!preg_match('/^[a-z][a-z0-9_]*$/D', $suffix)) {
            throw new \InvalidArgumentException('Invalid table name.', 422);
        }
        $name = $this->prefix . 'ordenowa_procurement_' . $suffix;
        if (strlen($name) > 64) { throw new \InvalidArgumentException('Database table prefix is too long.', 422); }
        return '`' . $name . '`';
    }

    public function quote(string $value): string
    {
        if ($this->connection instanceof \PDO) {
            $quoted = $this->connection->quote($value);
            if ($quoted === false) {
                throw new \RuntimeException('Database quoting failed.');
            }
            return $quoted;
        }
        return "'" . $this->connection->escape($value, true) . "'";
    }

    public function execute(string $sql): void
    {
        try {
            $result = $this->connection instanceof \PDO
                ? $this->connection->exec($sql)
                : $this->connection->execute($sql, false);
            if ($result === false) {
                $code = method_exists($this->connection, 'getNumberError') ? (int)$this->connection->getNumberError() : 0;
                throw new \RuntimeException('Database write failed.', $code);
            }
        } catch (\Throwable $error) {
            $code = (int)$error->getCode();
            throw new \RuntimeException('Database write failed.', in_array($code, [1205,1213], true) ? $code : 0, $error);
        }
    }

    public function all(string $sql): array
    {
        try {
            $result = $this->connection instanceof \PDO
                ? $this->connection->query($sql)->fetchAll(\PDO::FETCH_ASSOC)
                : $this->connection->executeS($sql, true, false);
            if (!is_array($result)) {
                $code = method_exists($this->connection, 'getNumberError') ? (int)$this->connection->getNumberError() : 0;
                throw new \RuntimeException('Database read failed.', $code);
            }
            return $result;
        } catch (\Throwable $error) {
            $code = (int)$error->getCode();
            throw new \RuntimeException('Database read failed.', in_array($code, [1205,1213], true) ? $code : 0, $error);
        }
    }

    public function one(string $sql): ?array
    {
        $rows = $this->all($sql);
        return $rows[0] ?? null;
    }

    public function value(string $sql): mixed
    {
        $row = $this->one($sql);
        return $row === null ? null : reset($row);
    }

    public function insertId(): int
    {
        return (int) ($this->connection instanceof \PDO
            ? $this->connection->lastInsertId() : $this->connection->Insert_ID());
    }

    public function transaction(callable $callback): mixed
    {
        $level = $this->depth;
        $this->execute($level === 0 ? 'START TRANSACTION' : 'SAVEPOINT ordenowa_' . $level);
        ++$this->depth;
        try {
            $result = $callback($this);
            $this->execute($level === 0 ? 'COMMIT' : 'RELEASE SAVEPOINT ordenowa_' . $level);
            --$this->depth;
            return $result;
        } catch (\Throwable $error) {
            --$this->depth;
            try {
                $this->execute($level === 0 ? 'ROLLBACK' : 'ROLLBACK TO SAVEPOINT ordenowa_' . $level);
            } catch (\Throwable $rollbackError) {
                throw new \RuntimeException('Database rollback failed.', 0, $rollbackError);
            }
            throw $error;
        }
    }
}
