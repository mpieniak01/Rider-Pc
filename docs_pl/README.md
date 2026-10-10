# Dokumentacja Rider-PC

Rider-PC dostarcza panel operatora, przetwarzanie AI i narzędzia PC dla Rider-Pi.
Fizyczne wykonanie pozostaje na robocie. Venom jest planowanym filarem
nadrzędnego sterowania; integracja pozostaje odłożona.

## Zacznij tutaj

- [Wizja projektu](PROJECT.md), [architektura](ARCHITEKTURA.md), [szybki start](SZYBKI_START.md).
- [Development](development.md), [współtworzenie](CONTRIBUTING.md).
- [Polityka dokumentacji](POLITYKA_DOKUMENTACJI.md), [dokumentacja angielska](../docs/README.md).

## Interfejsy i konfiguracja

- [Bezpieczny klient i zgoda operatora](BEZPIECZNY_KLIENT_ROBOTA.md).

- [Integracja Pi ↔ PC](INTEGRACJA_OFFLOAD_PC.md).
- [Konfiguracja](KONFIGURACJA.md), [modele AI](KONFIGURACJA_MODELI_AI.md), [kolejka](KONFIGURACJA_KOLEJKI_ZADAN.md).
- [Monitoring](KONFIGURACJA_MONITORINGU.md), [usługi i zasoby](ZARZADZANIE_USLUGAMI_I_ZASOBAMI.md), [konfiguracja sieci](KONFIGURACJA_BEZPIECZENSTWA.md).
- [Indeks API](api-specs/README.md), [sterowanie](api-specs/STEROWANIE.md), [nawigacja](api-specs/NAWIGATOR.md).
- [Replikacja UI/API](NOTATKI_REPLIKACJI.md), [styleguide](styleguide.md), [Google Assistant](google-assistant-integration.md).

Backlogi operacyjne, raporty faz, audyty i wyniki sprawdzeń konkretnej sesji
są lokalnymi plikami w ignorowanych katalogach. Test z mockiem i dane z cache
nie potwierdzają rzeczywistego działania modelu ani fizycznego robota.

Wersja polska jest punktem wyjścia; aktualizujemy też instrukcje EN.
Lokalne plany i raporty utrzymujemy tylko w `docs_pl/_to_do/` i `docs_pl/_done/`.
