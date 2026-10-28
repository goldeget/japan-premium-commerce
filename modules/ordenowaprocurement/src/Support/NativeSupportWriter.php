<?php

declare(strict_types=1);
namespace Ordenowa\Procurement\Support;

/** Native models use the same primary Db connection as the caller's transaction. */
final class NativeSupportWriter
{
    public function thread(array $trusted): int
    {
        if (!class_exists('CustomerThread') || !class_exists('CustomerMessage')) throw new \RuntimeException('Support unavailable.',503);
        $thread = new \CustomerThread();
        foreach ($trusted as $field => $value) $thread->$field = $value;
        $thread->id_order = 0;
        $thread->status = 'open';
        $thread->token = bin2hex(random_bytes(6));
        if (!$thread->add() || (int)$thread->id < 1) throw new \RuntimeException('Support unavailable.',503);
        return (int)$thread->id;
    }

    public function message(int $thread, string $body): int
    {
        $message = new \CustomerMessage();
        $message->id_customer_thread = $thread;
        $message->id_employee = 0;
        $message->id_product = 0;
        $message->message = htmlspecialchars($body, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
        $message->private = 0;
        $message->file_name = '';
        $message->ip_address = '0';
        $message->user_agent = '';
        $message->read = 0;
        if (!$message->add() || (int)$message->id < 1) throw new \RuntimeException('Support unavailable.',503);
        return (int)$message->id;
    }
}
