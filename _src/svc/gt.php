<?php
// Запасной прокси ГИС Торги для сервера Залог-Деска (основной — функция Яндекс Облака, yandex-function/index.py
// в zalog-desk). Тот же протокол: key + path + параметры запроса; для файлов лота (/new/file-store/v1/) — range,
// ответ base64 текстом с заголовками X-Total и X-Name. Ключ хранится только хешем; сам ключ — в .env Залог-Деска
// (TORGI_PROXY2_KEY). Ходит только на torgi.gov.ru и только по двум открытым путям.
const KEY_SHA256 = '3966f034d26022336ac45bd317a2ed1472bd80fb2c78d5d2409d285d87bfab27';
define('BASE', getenv('TORGI_BASE') ?: 'https://torgi.gov.ru');  // подмена только для тестов
const UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36';

header('X-Robots-Tag: noindex');
header('Cache-Control: no-store');

function fail($code, $msg) {
    http_response_code($code);
    header('Content-Type: text/plain; charset=utf-8');
    exit($msg);
}

// $_GET склеивает повторяющиеся параметры, а ГИС Торги их понимает — разбираем строку запроса сами
$key = $path = $range = '';
$params = [];
foreach (explode('&', $_SERVER['QUERY_STRING'] ?? '') as $pair) {
    if ($pair === '') continue;
    $kv = explode('=', $pair, 2);
    $k = urldecode($kv[0]);
    $v = urldecode($kv[1] ?? '');
    if ($k === 'key') $key = $v;
    elseif ($k === 'path') $path = $v;
    elseif ($k === 'range') $range = $v;
    elseif ($k !== 'b64') $params[] = rawurlencode($k) . '=' . rawurlencode($v);
}
if (!hash_equals(KEY_SHA256, hash('sha256', $key))) fail(403, 'forbidden');
if (strpos($path, '..') !== false || !preg_match('#^/new/(api/public|file-store/v1)/[A-Za-z0-9_./-]*$#', $path)) {
    fail(400, 'bad path');
}
$file = strpos($path, '/new/file-store/v1/') === 0;
if ($file && !preg_match('/^\d{1,10}-\d{1,10}$/', $range)) $range = '0-1999999';

$headers = [];
$ch = curl_init(BASE . $path . ($params && !$file ? '?' . implode('&', $params) : ''));
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_FOLLOWLOCATION => false,
    CURLOPT_CONNECTTIMEOUT => 10,
    CURLOPT_TIMEOUT => 25,
    // сертификат torgi.gov.ru выпущен российским УЦ, которого нет в стандартном наборе
    CURLOPT_SSL_VERIFYPEER => false,
    CURLOPT_SSL_VERIFYHOST => 0,
    CURLOPT_HTTPHEADER => array_merge(['User-Agent: ' . UA], $file ? ['Range: bytes=' . $range] : ['Accept: application/json']),
    CURLOPT_HEADERFUNCTION => function ($c, $line) use (&$headers) {
        $p = explode(':', $line, 2);
        if (count($p) === 2) $headers[strtolower(trim($p[0]))] = trim($p[1]);
        return strlen($line);
    },
]);
$body = curl_exec($ch);
$code = (int) curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
$err = curl_error($ch);
curl_close($ch);
if ($body === false || $code === 0) fail(502, 'proxy error: ' . $err);

if ($file) {
    if ($code >= 400) fail(502, 'file error: HTTP ' . $code);
    $body = substr($body, 0, 2100000);
    $total = $headers['content-range'] ?? '';
    $total = $total !== '' ? substr($total, strrpos($total, '/') + 1) : (string) strlen($body);
    header('Content-Type: text/plain');
    header('X-Total: ' . $total);
    header('X-Name: ' . rawurlencode($headers['content-disposition'] ?? ''));
    exit(base64_encode($body));
}
http_response_code($code);
header('Content-Type: ' . ($code < 400 ? 'application/json' : 'text/plain; charset=utf-8'));
exit($code < 400 ? $body : substr($body, 0, 500));
