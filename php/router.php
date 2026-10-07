<?php
declare(strict_types=1);
// PHP is the public local entry point. Python owns authentication and data processing.
$root = dirname(__DIR__);
$uri = $_SERVER['REQUEST_URI'] ?? '/';
$path = parse_url($uri, PHP_URL_PATH);
header('X-Content-Type-Options: nosniff');
header('X-Frame-Options: DENY');
header('Referrer-Policy: same-origin');
header("Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'");

if (is_string($path) && str_starts_with($path, '/api/')) {
    header('Cache-Control: no-store');
    if (!preg_match('~^/api/[a-zA-Z0-9/_-]+$~D', $path)) {
        http_response_code(400);
        header('Content-Type: application/json; charset=utf-8');
        echo json_encode(['detail' => 'Ruta inválida.']);
        return;
    }
    $method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
    if (!in_array($method, ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD'], true)) {
        http_response_code(405);
        header('Content-Type: application/json; charset=utf-8');
        echo json_encode(['detail' => 'Método no permitido.']);
        return;
    }
    $body = file_get_contents('php://input', false, null, 0, 16 * 1024 * 1024 + 1);
    if ($body === false || strlen($body) > 16 * 1024 * 1024) {
        http_response_code(413);
        header('Content-Type: application/json; charset=utf-8');
        echo json_encode(['detail' => 'Solicitud demasiado grande. Archivos hasta 10 MiB.']);
        return;
    }
    $headers = ["Connection: close"];
    foreach (['CONTENT_TYPE'=>'Content-Type', 'HTTP_COOKIE'=>'Cookie',
              'HTTP_X_REQUESTED_WITH'=>'X-Requested-With', 'HTTP_ORIGIN'=>'Origin'] as $key=>$name) {
        if (isset($_SERVER[$key])) {
            $value = str_replace(["\r", "\n"], '', (string)$_SERVER[$key]);
            $headers[] = $name . ': ' . $value;
        }
    }
    $headers[] = 'Content-Length: ' . strlen($body);
    // The destination is fixed: user input cannot choose an external server.
    $context = stream_context_create(['http' => [
        'method' => $method, 'header' => implode("\r\n", $headers),
        'content' => $body, 'ignore_errors' => true, 'timeout' => 30,
        'follow_location' => 0,
    ]]);
    $response = @file_get_contents('http://127.0.0.1:8010' . $uri, false, $context);
    if ($response === false) {
        http_response_code(502);
        header('Content-Type: application/json; charset=utf-8');
        echo json_encode(['detail' => 'El servicio Python no responde. Inicia el proyecto con start.py.']);
        return;
    }
    foreach ($http_response_header ?? [] as $line) {
        if (preg_match('~^HTTP/\S+\s+(\d{3})~', $line, $match)) {
            http_response_code((int)$match[1]);
        } elseif (preg_match('~^(Content-Type|Content-Disposition|Set-Cookie|Cache-Control):~i', $line)) {
            header($line, false);
        }
    }
    echo $response;
    return;
}

$assets = ['/app.js'=>'application/javascript', '/styles.css'=>'text/css', '/favicon.svg'=>'image/svg+xml'];
if (isset($assets[$path])) {
    header('Content-Type: ' . $assets[$path] . '; charset=utf-8');
    readfile($root . '/web' . $path);
    return;
}
if ($path === '/' || $path === '/index.php') {
    header('Content-Type: text/html; charset=utf-8');
    readfile($root . '/web/index.html');
    return;
}
http_response_code(404);
header('Content-Type: text/plain; charset=utf-8');
echo 'Página no encontrada.';
