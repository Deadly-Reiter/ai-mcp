# Agent Orchestration Phase 2 AP2 — Fix Build

Этот архив содержит исправления для двух падавших тестов и предупреждения PyJWT о слишком коротком HMAC-секрете. В исходном плане Phase 2 AP2 выступает как delegation spend policy layer поверх orchestration, wallets и MCP/x402, поэтому фиксы касаются одновременно retry/degraded routing и безопасной подписи policy tokens. [file:1]

## Что исправлено

- Исправлен `test_policy_rejection`: partial AP2 reject теперь переводит run в degraded branch, а `total_spent` считается по успешным authorized subtasks. [file:1]
- Исправлен `test_retry_then_degraded`: pending tasks и уже полученные results больше не теряются между retry-итерациями. [file:1]
- Устранён `InsecureKeyLengthWarning`: `AP2PolicyManager` требует секрет длиной не менее 32 байт для HS256. [file:1]
- Добавлен `main.py` для локального happy-path запуска. [file:1]

## Установка

```bash
unzip -o agent-orchestration-phase2-ap2-fix.zip
cd agent-orchestration-phase2-ap2
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Если у вас уже есть виртуальное окружение, всё равно выполните `pip install -e .`, потому что в этом fix-архиве явно добавлены `PyJWT` и `pytest-asyncio`.

## Переменная окружения

Перед тестами и запуском установите безопасный AP2 secret:

```bash
export AP2_USER_SECRET=0123456789abcdef0123456789abcdef
```

## Запуск тестов

```bash
pytest -q
```

Проверка только ранее падавших тестов:

```bash
pytest -q tests/test_policy_rejection.py tests/test_retry_degraded.py
```

## Демо запуск

```bash
python main.py
```

Ожидаемый happy-path результат:
- `stage: END`
- `degraded: False`
- `authorized_budget_total: 0.12`
- `total_spent: 0.085`
- `master_balance: 9.915`

## Ожидаемый тестовый результат

После фикса ожидается:
- `4 passed`
- без предупреждений `InsecureKeyLengthWarning`
- partial rejection и timeout сценарии корректно уходят в degraded execution, что соответствует вашей Phase 2 multi-agent модели. [file:1]
