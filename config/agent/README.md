# Konfiguracja GitHub Copilot Coding Agent

Ten katalog zawiera artefakty wymagane do współpracy z agentami Copilot opisanymi w [dokumentacji GitHub](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent).

## Pliki

| Plik | Cel |
| --- | --- |
| `constraints.txt` | Zbiór ograniczeń wersji instalowanych pakietów Pythona dla konfiguracji agenta. |
| `requirements-test.txt` | Lekki zestaw zależności, który wskazuje na `requirements-ci.txt`. Instalowany jest przed uruchomieniem testów. |
| `run_tests.sh` | Scentralizowany skrypt (wykorzystywany również przez Copilot) tworzący środowisko `.venv-agent`, instalujący zależności i uruchamiający podstawowe testy `pytest`. |

## Wskazówki użycia

1. Uruchom `./config/agent/run_tests.sh`, aby odtworzyć identyczny przepływ jak w Copilot coding agent.
2. W przypadku aktualizacji zależności pamiętaj o zsynchronizowaniu `requirements-ci.txt` oraz `constraints.txt`.
3. Workflow `.github/workflows/copilot-setup-steps.yml` korzysta z powyższych plików podczas przygotowywania środowiska agenta.
