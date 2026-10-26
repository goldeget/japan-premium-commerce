<?php

declare(strict_types=1);

// Standalone controller behavior fixture; also included by assignment_repository.php in Actions.
if (!class_exists('ModuleAdminController', false)) {
    class ModuleAdminController
    {
        public array $tabAccess = ['view' => true, 'add' => true, 'edit' => true];
        public function viewAccess(): bool { return true; }
        public function access(string $operation): bool { return true; }
    }
}
require_once dirname(__DIR__, 2) . '/modules/kuraneabackoffice/controllers/admin/AdminKuraneaSupportAssignmentsController.php';

$statusControllerClass = new ReflectionClass(AdminKuraneaSupportAssignmentsController::class);
$statusController = $statusControllerClass->newInstanceWithoutConstructor();
$statusRenderTable = $statusControllerClass->getMethod('renderThreadTable');
foreach (['open' => '접수', 'closed' => '종결', 'pending1' => '보류 1', 'pending2' => '보류 2', '<script>unknown</script>' => '상태 확인 필요'] as $nativeStatus => $koreanStatus) {
    $statusThread = ['id_customer_thread' => 17, 'status' => $nativeStatus, 'date_add' => '2026-01-01 00:00:00'];
    $statusHtml = $statusRenderTable->invoke($statusController, [$statusThread], [], '/admin/index.php?token=synthetic', 'synthetic');
    if (!str_contains($statusHtml, '<td>' . $koreanStatus . '</td>')) {
        throw new RuntimeException('Support inquiry status must render a Korean label.');
    }
    if (str_contains($statusHtml, '<td>' . $nativeStatus . '</td>') || str_contains($statusHtml, '<script>')) {
        throw new RuntimeException('Support inquiry status must not expose raw or unknown status values.');
    }
    if ($statusThread['status'] !== $nativeStatus) {
        throw new RuntimeException('Rendering must preserve the stored native status value.');
    }
}
fwrite(STDOUT, "PASS: Korean support state rendering and safe unknown state fallback.\n");
