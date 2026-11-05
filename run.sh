#!/bin/bash

echo "=== Запуск тестов ==="

if ! python3.10 -m unittest discover -s tests -v; then
    echo "Тесты не пройдены. Запуск программы отменён."
    exit 1
fi

echo ""
echo "=== Запуск программы ==="

python3.10 src/main.py --config config.yaml