<?php
// Проверка, что PHP на хостинге работает и в нём есть curl (для запасного прокси ГИС Торги gt.php).
header('Content-Type: text/plain');
header('X-Robots-Tag: noindex');
echo 'ok php=' . PHP_VERSION . ' curl=' . (function_exists('curl_init') ? '1' : '0');
