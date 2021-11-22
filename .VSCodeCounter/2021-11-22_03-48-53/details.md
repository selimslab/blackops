# Details

Date : 2021-11-22 03:48:53

Directory /Users/selim/Desktop/ops

Total : 62 files,  4193 codes, 158 comments, 1000 blanks, all 5351 lines

[summary](results.md)

## Files
| filename | language | code | comment | blank | total |
| :--- | :--- | ---: | ---: | ---: | ---: |
| [.flake8](/.flake8) | Ini | 3 | 0 | 1 | 4 |
| [.pre-commit-config.yaml](/.pre-commit-config.yaml) | YAML | 25 | 0 | 6 | 31 |
| [Dockerfile](/Dockerfile) | Docker | 13 | 3 | 11 | 27 |
| [README.md](/README.md) | Markdown | 13 | 0 | 14 | 27 |
| [blackops/__init__.py](/blackops/__init__.py) | Python | 1 | 0 | 1 | 2 |
| [blackops/api/__init__.py](/blackops/api/__init__.py) | Python | 1 | 0 | 1 | 2 |
| [blackops/api/auth.py](/blackops/api/auth.py) | Python | 14 | 0 | 5 | 19 |
| [blackops/api/basics.py](/blackops/api/basics.py) | Python | 0 | 35 | 14 | 49 |
| [blackops/api/handlers.py](/blackops/api/handlers.py) | Python | 59 | 8 | 41 | 108 |
| [blackops/api/main.py](/blackops/api/main.py) | Python | 17 | 0 | 10 | 27 |
| [blackops/api/models/__init__.py](/blackops/api/models/__init__.py) | Python | 1 | 0 | 1 | 2 |
| [blackops/api/models/stg.py](/blackops/api/models/stg.py) | Python | 83 | 1 | 42 | 126 |
| [blackops/api/models/validate.py](/blackops/api/models/validate.py) | Python | 0 | 0 | 1 | 1 |
| [blackops/api/routers.py](/blackops/api/routers.py) | Python | 48 | 24 | 26 | 98 |
| [blackops/api/static/index.html](/blackops/api/static/index.html) | HTML | 62 | 0 | 25 | 87 |
| [blackops/domain/__init__.py](/blackops/domain/__init__.py) | Python | 1 | 0 | 1 | 2 |
| [blackops/domain/models/__init__.py](/blackops/domain/models/__init__.py) | Python | 1 | 0 | 1 | 2 |
| [blackops/domain/models/asset.py](/blackops/domain/models/asset.py) | Python | 15 | 0 | 8 | 23 |
| [blackops/domain/models/exchange.py](/blackops/domain/models/exchange.py) | Python | 30 | 0 | 12 | 42 |
| [blackops/domain/models/stg.py](/blackops/domain/models/stg.py) | Python | 10 | 2 | 8 | 20 |
| [blackops/domain/symbols.py](/blackops/domain/symbols.py) | Python | 45 | 0 | 6 | 51 |
| [blackops/exchanges/binance/__init__.py](/blackops/exchanges/binance/__init__.py) | Python | 1 | 0 | 1 | 2 |
| [blackops/exchanges/binance/base.py](/blackops/exchanges/binance/base.py) | Python | 29 | 0 | 8 | 37 |
| [blackops/exchanges/binance/factory.py](/blackops/exchanges/binance/factory.py) | Python | 5 | 0 | 5 | 10 |
| [blackops/exchanges/btcturk/__init__.py](/blackops/exchanges/btcturk/__init__.py) | Python | 1 | 0 | 1 | 2 |
| [blackops/exchanges/btcturk/base.py](/blackops/exchanges/btcturk/base.py) | Python | 55 | 4 | 19 | 78 |
| [blackops/exchanges/btcturk/factory.py](/blackops/exchanges/btcturk/factory.py) | Python | 7 | 0 | 5 | 12 |
| [blackops/exchanges/btcturk/manual.py](/blackops/exchanges/btcturk/manual.py) | Python | 65 | 0 | 26 | 91 |
| [blackops/exchanges/btcturk/real.py](/blackops/exchanges/btcturk/real.py) | Python | 7 | 1 | 5 | 13 |
| [blackops/exchanges/btcturk/testnet.py](/blackops/exchanges/btcturk/testnet.py) | Python | 38 | 0 | 12 | 50 |
| [blackops/main.py](/blackops/main.py) | Python | 0 | 0 | 1 | 1 |
| [blackops/stgs/__init__.py](/blackops/stgs/__init__.py) | Python | 1 | 0 | 1 | 2 |
| [blackops/stgs/base.py](/blackops/stgs/base.py) | Python | 0 | 0 | 1 | 1 |
| [blackops/stgs/sliding_window.py](/blackops/stgs/sliding_window.py) | Python | 241 | 31 | 104 | 376 |
| [blackops/stgs/sliding_window_with_bridge.py](/blackops/stgs/sliding_window_with_bridge.py) | Python | 58 | 0 | 18 | 76 |
| [blackops/streams/__init__.py](/blackops/streams/__init__.py) | Python | 1 | 0 | 1 | 2 |
| [blackops/streams/binance.py](/blackops/streams/binance.py) | Python | 17 | 3 | 11 | 31 |
| [blackops/streams/btcturk.py](/blackops/streams/btcturk.py) | Python | 25 | 1 | 16 | 42 |
| [blackops/taskq/__init__.py](/blackops/taskq/__init__.py) | Python | 1 | 0 | 1 | 2 |
| [blackops/taskq/redis.py](/blackops/taskq/redis.py) | Python | 6 | 1 | 6 | 13 |
| [blackops/taskq/task_ctx.py](/blackops/taskq/task_ctx.py) | Python | 32 | 1 | 10 | 43 |
| [blackops/taskq/tasks.py](/blackops/taskq/tasks.py) | Python | 61 | 12 | 39 | 112 |
| [blackops/trader/__init__.py](/blackops/trader/__init__.py) | Python | 1 | 0 | 1 | 2 |
| [blackops/trader/factory.py](/blackops/trader/factory.py) | Python | 143 | 2 | 51 | 196 |
| [blackops/util/is_unique.py](/blackops/util/is_unique.py) | Python | 13 | 0 | 13 | 26 |
| [blackops/util/logger.py](/blackops/util/logger.py) | Python | 29 | 5 | 22 | 56 |
| [blackops/util/numbers.py](/blackops/util/numbers.py) | Python | 2 | 0 | 2 | 4 |
| [blackops/util/push.py](/blackops/util/push.py) | Python | 9 | 0 | 3 | 12 |
| [blackops/util/push_events.py](/blackops/util/push_events.py) | Python | 3 | 0 | 3 | 6 |
| [blackops/util/ws.py](/blackops/util/ws.py) | Python | 22 | 6 | 9 | 37 |
| [docker-compose.yml](/docker-compose.yml) | YAML | 7 | 11 | 5 | 23 |
| [docker-entrypoint.sh](/docker-entrypoint.sh) | Shell Script | 3 | 4 | 8 | 15 |
| [exp/aiotask.py](/exp/aiotask.py) | Python | 8 | 0 | 8 | 16 |
| [poetry.lock](/poetry.lock) | toml | 2,524 | 0 | 217 | 2,741 |
| [requirements.txt](/requirements.txt) | pip requirements | 80 | 0 | 1 | 81 |
| [scripts/clean.sh](/scripts/clean.sh) | Shell Script | 3 | 3 | 5 | 11 |
| [setup-dev.sh](/setup-dev.sh) | Shell Script | 5 | 0 | 7 | 12 |
| [static/index.html](/static/index.html) | HTML | 29 | 0 | 14 | 43 |
| [static/logs.html](/static/logs.html) | HTML | 155 | 0 | 80 | 235 |
| [tests/__init__.py](/tests/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [tests/realtime.py](/tests/realtime.py) | Python | 29 | 0 | 15 | 44 |
| [wtf.yml](/wtf.yml) | YAML | 35 | 0 | 9 | 44 |

[summary](results.md)