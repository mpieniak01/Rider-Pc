# Zarządzanie usługami i zasobami (systemd) – Rider-PC

Dokument operacyjny porządkujący autostart, profile uruchomieniowe, zależności usług i rezerwacje zasobów (kamera, mikrofon, głośnik, LCD). Powstał na bazie obecnego zestawu unitów `rider-*.service` widocznych w UI sterowania.

## Profile uruchomieniowe (targety)

| Profil/target (propozycja) | Co uruchamia | Autostart | Zastosowanie | Komenda start/stop |
| --- | --- | --- | --- | --- |
| `rider-core.target` | `rider-api`, `rider-broker`, `rider-web-bridge` | TAK | Minimalne sterowanie i monitoring (REST/SSE + mostek ZMQ) | `systemctl enable --now rider-core.target` / `systemctl stop rider-core.target` |
| `rider-manual.target` | `core` + `rider-cam-preview` (surowy podgląd) | NIE | Jazda ręczna z podglądem kamery bez filtrów | `systemctl start rider-manual.target` / `systemctl stop rider-manual.target` |
| `rider-autonomy.target` | `core` + `rider-navigator`, `rider-mapper`, `rider-obstacle`, `rider-odometry` | NIE | Tryb autonomiczny / rekonesans, komplet percepcji ruchu | `systemctl start rider-autonomy.target` / `systemctl stop rider-autonomy.target` |
| `rider-voice.target` | `rider-voice-web` **lub** `rider-voice` (jeden stos na raz) | NIE | Sterowanie głosowe lokalne lub web | `systemctl start rider-voice.target` / `systemctl stop rider-voice.target` |
| `rider-diagnostics.target` | `rider-edge-preview`, `rider-ssd-preview`, inne preview testowe | NIE (tylko czasowo) | Diagnostyka obrazu/obciążenia, krótkie sesje | `systemctl start rider-diagnostics.target` / `systemctl stop rider-diagnostics.target` |

## Rekomendacje autostartu i rola usług

| Usługa (systemd unit) | Rola | Autostart (zalec.) | Włączać w trybie | Zasoby krytyczne / uwagi |
| --- | --- | --- | --- | --- |
| `rider-api.service` | Serwer REST/SSE sterowania i monitoringu | TAK | Wszystkie | CPU; brak sprzętowych blokad |
| `rider-broker.service` | Mostek ZMQ między modułami | TAK | Wszystkie | CPU; utrzymuje magistralę |
| `rider-web-bridge.service` | Mostek HTTP↔ZMQ dla komend ruchu | TAK | Wszystkie | CPU; bez zasobów fizycznych |
| `rider-cam-preview.service` | Surowy podgląd kamery | NIE (tylko manual) | Manual, diagnostyka lekka | Kamera (wyłączny dostęp) |
| `rider-edge-preview.service` | Podgląd kamery z filtrem krawędziowym | NIE (diag) | Diagnostyka obrazu | Kamera + CPU/GPU; koliduje z innymi podglądami |
| `rider-ssd-preview.service` | Podgląd SSD z ramkami detekcji | NIE (diag) | Diagnostyka obrazu | Kamera + GPU; tylko 1 usługa kamerowa naraz |
| `rider-tracker.service` | Wizyjny tracker (twarz/dłoń, MediaPipe) | NIE (opcjonalnie) | Manual z “Follow Face/Hand” | Kamera + GPU/CPU; preferowany nad podglądami |
| `rider-vision.service` | Dispatcher wizyjny (YOLO/SSD) | NIE (opcjonalnie) | Autonomia/Recon jeśli offload na PC | Kamera + GPU/CPU; koliduje z podglądami |
| `rider-navigator.service` | Nawigator autonomiczny (Recon) | NIE | Autonomia | CPU; zależy na danych mapy/odometrii |
| `rider-mapper.service` | SLAM/mapowanie zajętości | NIE | Autonomia | CPU; wymaga sensora pozycji i kamery (pośrednio) |
| `rider-obstacle.service` | Detekcja przeszkód (ROI) | NIE | Autonomia | CPU/GPU jeśli używa wizji |
| `rider-odometry.service` | Odometria (śl. pozycji) | NIE | Autonomia | CPU; wejścia enkoderów/IMU (bez blokady kamery) |
| `rider-motion-bridge.service` | Mostek ruch/XGO – telemetria i sterowanie | AUTOSTART ZALEŻNY* | Core + Autonomia | CPU; krytyczny dla komend ruchu |
| `rider-google-bridge.service` | Integracja Google Home | NIE | Dodatki/Integracje | Mikrofon/głośnik pośrednio; sieć zewnętrzna |
| `rider-voice-web.service` | Webowy stos głosu (Piper TTS + Vosk ASR) | NIE | Voice (web) | Mikrofon + głośnik; koliduje z `rider-voice.service` |
| `rider-voice.service` | CLI asystent głosowy lokalny | NIE | Voice (CLI) | Mikrofon + głośnik; konflikt z `rider-voice-web.service` |

* Jeśli mostek ruchu jest wymagany zawsze dla sterowania, można włączyć go w `core.target`; w przeciwnym razie dodać do `manual/autonomy`.

## Rezerwacja zasobów (kamera, audio, LCD)

| Zasób | Usługi korzystające | Reguła | Notatka operacyjna |
| --- | --- | --- | --- |
| Kamera (`/dev/video0`) | `rider-cam-preview`, `rider-edge-preview`, `rider-ssd-preview`, `rider-tracker`, `rider-vision` | `Conflicts=` między wszystkimi usługami kamerowymi lub lock w `/run/rider/camera.lock` | UI: przed startem pyta o zwolnienie zasobu; restart po zwolnieniu |
| Mikrofon | `rider-voice-web`, `rider-voice`, `rider-google-bridge` (jeśli nasłuch) | `Conflicts=rider-voice-web.service rider-voice.service` | Wybieraj jeden stos głosowy; drugi pozostaje `inactive` |
| Głośnik | `rider-voice-web`, `rider-voice`, `rider-google-bridge` | Jak wyżej + limiter głośności w UI | Wstrzymuj TTS przy zmianie stosu |
| LCD 2" | Usługa wyświetlająca status (jeśli istnieje) | `Conflicts=` gdy pojawią się inne konsumenty LCD | Aktualnie brak konkurencji |

Przykładowy fragment override dla usług kamerowych:

```
[Unit]
Requires=dev-video0.device
After=dev-video0.device
Conflicts=rider-cam-preview.service rider-edge-preview.service rider-ssd-preview.service rider-vision.service

[Service]
Restart=on-failure
RestartSec=1
StartLimitIntervalSec=60
StartLimitBurst=5
```

## Procedury operacyjne

| Czynność | Kroki | Uwagi |
| --- | --- | --- |
| Start trybu ręcznego | `systemctl start rider-manual.target` | W razie blokady kamery – zatrzymaj preview diag. |
| Start trybu autonomicznego | `systemctl start rider-autonomy.target` | Upewnij się, że offload wizji nie blokuje kamery. |
| Włączenie sterowania głosowego | `systemctl start rider-voice.target` | Sprawdź, który stos (web/CLI) jest wybrany; drugi pozostaje wyłączony. |
| Diagnostyka obrazu | `systemctl start rider-diagnostics.target`, po testach `systemctl stop rider-diagnostics.target` | Krótkie sesje, bo obciąża GPU/CPU i blokuje kamerę. |
| Zwolnienie zasobu | `systemctl stop <usługa_kolidująca>` lub przycisk „Zwolnij” w UI | Po zwolnieniu ponownie uruchom docelową usługę. |

## Minimalne ustawienia unitów (zalecenia)

- `Restart=on-failure`, `RestartSec=1`, `StartLimitIntervalSec` + `StartLimitBurst` aby uniknąć flappingu.
- `After=network.target` oraz `After=dev-video0.device` dla usług kamerowych.
- Usługi opcjonalne (`voice`, preview, integracje) – bez autostartu.
- Autostart tylko w `core.target`; pozostałe uruchamiane przez targety trybów lub przyciski w UI.

## Checklist wdrożenia porządku

1. Wyłącz autostart wszystkiego poza `rider-core.target` (API, broker, web-bridge).
2. Utwórz targety: `rider-manual.target`, `rider-autonomy.target`, `rider-voice.target`, `rider-diagnostics.target`.
3. Dodaj `Conflicts` (lub lock) dla wszystkich usług kamerowych; analogicznie dla dwóch stosów głosu.
4. Ustaw limity restartów i `Restart=on-failure` w unitach optional/previews.
5. W UI: przed startem usługi sprawdzaj dostępność zasobu i proponuj „Zwolnij zasób → Start”.
6. Dodaj endpoint `/health` w `rider-api` raportujący stany unitów i locki zasobów do widoku diagnostycznego.
