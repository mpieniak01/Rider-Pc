# Zarządzanie usługami i zasobami (systemd) – Rider-Pi (stan repo)

Dokument odtworzony na bazie realnych unitów i targetów z `systemd/` w Rider-Pi. Usunięto wymyślone targety (`rider-manual.target`, `rider-autonomy.target` itd.). Sekcja „Propozycje” na końcu pokazuje ewentualne brakujące profile, ale nadal są to rzeczy do utworzenia.

## Aktualne targety (istniejące w repo)

| Target | Co uruchamia (Wants/After) | Autostart | Zastosowanie | Komenda start/stop |
| --- | --- | --- | --- | --- |
| `rider-minimal.target` | Minimalny zestaw: broker, API, vision, splash/post-splash | TAK (WantedBy=multi-user.target) | Start podstawowy robota (web + bus + dispatcher) | `systemctl enable --now rider-minimal.target` / `systemctl stop rider-minimal.target` |
| `rider-dev.target` | `jupyter.service` (+ zależności GUI) | NIE (enable ręcznie) | Profil deweloperski z JupyterLab | `systemctl start rider-dev.target` / `systemctl stop rider-dev.target` |

## Usługi z repo i zalecenia autostartu

| Usługa (systemd unit) | Rola | Autostart (zalec.) | Zasoby / uwagi | Powiązane funkcje w UI |
| --- | --- | --- | --- | --- |
| `rider-api.service` | API HTTP/SSE | TAK (core) | CPU; After=network-online | Wszystkie kafelki API/zdrowie |
| `rider-broker.service` | Broker ZMQ (XSUB/XPUB) | TAK (core) | CPU; After=network-online | Wszystkie funkcje ruchu/wizji |
| `rider-web-bridge.service` | HTTP→ZMQ mostek ruchu | TAK (core) | CPU; Wants=network-online | Sterowanie ruchem z UI |
| `rider-vision.service` | Vision Dispatcher | TAK (core/minimal) | Kamera/GPU; może kolidować z preview/tracker | Podstawowy podgląd/analiza w wizji |
| `rider-vision-offload.service` | Dispatcher offload | NIE (opcjonalny) | GPU/CPU; jeśli używasz offloadu | Offload wizji |
| `rider-choreographer.service` | Orkiestracja zdarzeń | NIE/TRYB | CPU; zależny od brokera | Automaty/Pilot eventów |
| `rider-motion-bridge.service` | Ruch/XGO – telemetria i sterowanie | TAK (ruch) | CPU; After=broker | Wysyłanie komend ruchu z UI |
| `rider-odometry.service` | Odometria | TAK (ruch/autonomia) | CPU; After=broker, motion-bridge | Diagnostyka pozycji |
| `rider-mapper.service` | SLAM / mapa zajętości | NIE/TRYB | CPU; After=broker, odometry | Tryb rekonesansu/autonomia |
| `rider-obstacle.service` | Detekcja przeszkód (ROI na edge preview) | NIE/TRYB | Kamera + CPU/GPU; After=edge-preview | Tryb rekonesansu/autonomia |
| `rider-navigator.service` | Nawigator autonomiczny | NIE/TRYB | CPU; After=broker/motion/vision/obstacle/odometry/mapper | Tryb rekonesansu (autonomiczny) |
| `rider-cam-preview.service` | Podgląd kamery surowy | NIE (diag/manual) | Kamera – wyłączny dostęp | Podgląd kamery (kafel) |
| `rider-edge-preview.service` | Podgląd z filtrem krawędziowym | NIE (diag) | Kamera + CPU/GPU; koliduje z innymi preview | Podgląd z filtrem (diag) |
| `rider-ssd-preview.service` | Podgląd SSD z ramkami | NIE (diag) | Kamera + GPU; 1 usługa kamerowa naraz | Podgląd SSD (diag) |
| `rider-tracker.service` | Tracker MediaPipe (twarz/dłoń) | NIE (feature) | Kamera + GPU/CPU; preferowany vs preview | `Śledź Twarz` / `Śledź Dłoń` |
| `rider-tracking-controller.service` | Sterownik obrotu „Follow Me” | NIE (feature) | CPU; After=tracker | `Śledź Twarz` / `Śledź Dłoń` (kontroler ruchu) |
| `rider-face.service` | Renderer twarzy na LCD | NIE/TRYB | LCD 2"; After=api | Wyświetlanie twarzy (LCD) |
| `rider-google-bridge.service` | Integracja Google Home | NIE (opcjonalne) | Sieć zewn.; może używać audio | Integracja GH |
| `rider-voice-web.service` | Web API głosu (Piper TTS + Vosk ASR) | NIE (włącz na żądanie) | Mikrofon + głośnik | Sterowanie głosowe (web) |
| `rider-voice.service` | CLI asystent głosowy (bazuje na voice-web) | NIE (włącz na żądanie) | Mikrofon + głośnik; After=voice-web | Sterowanie głosowe (CLI) |
| `rider-post-splash.service` | Post-splash (po API/IP) | Wraz z minimal | Lekka; WantedBy=rider-minimal.target | Ekran info po starcie |
| `rider-boot-splash.service` | Splash na starcie | Wraz z minimal | Lekka; cleanup + LCD off | Ekran startowy |
| `wifi-unblock.service` | Odblokowanie Wi‑Fi | TAK (system) | Uruchamiane przed siecią | — |
| `jupyter.service` | JupyterLab DEV | NIE (tylko dev target) | Używany przez `rider-dev.target` | Dev |

Legenda autostartu: “TAK (core)” – sugerowane w każdym starcie; “NIE/TRYB” – włącz w konkretnym profilu (autonomia/diag/feature). Kolumna „Powiązane funkcje w UI” mapuje kafelki: `Śledź Twarz/Śledź Dłoń` → tracker + tracking-controller; „Tryb rekonesansu (autonomiczny)” → navigator + obstacle + mapper + odometry (+ motion/vision jako zależności).

## Funkcje w UI a uruchamiane usługi

Kafelki „Funkcje” nie wykonują logiki ruchu/wizji samodzielnie – wywołują API Rider-Pi, które startuje/stopuje unity systemd. Jawne mapowanie przycisków Start/Stop:

| Funkcja w UI | `Start` uruchamia usługi | `Stop` zatrzymuje | Zasoby / konflikty | Uwagi operacyjne |
| --- | --- | --- | --- | --- |
| `Śledź Twarz (Follow Face)` | `rider-tracker.service`, `rider-tracking-controller.service`, `rider-motion-bridge.service` (+ core) | Te same: tracker + tracking-controller (+ motion-bridge jeśli nie wspólny) | Kamera, CPU/GPU; konflikt z innymi usługami kamerowymi (cam/edge/ssd/vision) | Upewnij się, że kamera wolna; gdy zajęta, zatrzymaj preview/vision lub użyj locka. Kontroler wysyła komendy ruchu przez motion-bridge. |
| `Śledź Dłoń (Follow Hand)` | Jak wyżej: `rider-tracker`, `rider-tracking-controller`, `rider-motion-bridge` (tracker w trybie dłoni) | Jak wyżej | Kamera, CPU/GPU; konflikt z preview/vision | Ten sam pipeline, inny tryb trackera; nie uruchamiaj równolegle z podglądami kamery. |
| `Tryb rekonesansu (autonomiczny)` | `rider-motion-bridge`, `rider-odometry`, `rider-mapper`, `rider-edge-preview`, `rider-obstacle`, `rider-vision`, `rider-navigator` (+ core) | Te same: navigator + obstacle + mapper + odometry + motion-bridge (+ vision/edge-preview jeśli startowane z trybu) | Kamera, CPU/GPU; konflikt z innymi podglądami (cam/ssd) | Edge-preview potrzebne dla obstacle; vision dla navigatora; odometry+mapper dla planowania. Przed startem zwolnij kamerę z innych usług. |

Jeśli UI otrzyma nowe kafelki, dodaj wiersz z listą unitów startowanych/przerywanych przez przyciski `Start`/`Stop`.

## Rezerwacja zasobów (stan vs. rekomendacja)

| Zasób | Usługi korzystające | Rekomendacja (do dodania) | Notatka operacyjna |
| --- | --- | --- | --- |
| Kamera (`/dev/video0`) | `rider-cam-preview`, `rider-edge-preview`, `rider-ssd-preview`, `rider-tracker`, `rider-vision` | Dodać `Conflicts=` między usługami kamerowymi lub lock `/run/rider/camera.lock` | Uruchamiaj tylko jedną usługę kamerową naraz; tracker ma priorytet nad preview |
| Mikrofon | `rider-voice-web`, `rider-voice`, `rider-google-bridge` (jeśli nasłuch) | `Conflicts=rider-voice-web.service rider-voice.service` | Wybierz jeden stos głosu; drugi pozostaje `inactive` |
| Głośnik | `rider-voice-web`, `rider-voice`, `rider-google-bridge` | Jak wyżej + limiter głośności w UI | Wstrzymaj TTS przy zmianie stosu |
| LCD 2" | `rider-face.service`, (splash/post-splash) | `Conflicts=` jeśli pojawią się inne konsumenty LCD | Aktualnie brak konkurencji |

Przykład override dla usług kamerowych:
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

## Procedury operacyjne (na bazie istniejących targetów)

| Czynność | Kroki | Uwagi |
| --- | --- | --- |
| Start profilu minimalnego | `systemctl start rider-minimal.target` | Podstawowy zestaw (broker+API+vision+splash) |
| Profil deweloperski | `systemctl start rider-dev.target` | Uruchamia Jupyter; zatrzymaj po sesji |
| Włączenie sterowania głosowego | `systemctl start rider-voice-web.service` (lub `.service` + `.socket`) | Upewnij się, że mikrofon/głośnik wolny; nie uruchamiaj równolegle `rider-voice.service` |
| Tryb „Follow Face/Hand” | `systemctl start rider-tracker.service rider-tracking-controller.service` | Jeśli kamera zajęta przez preview/vision – zwolnij zasób i ponów start |
| Tryb autonomiczny (ręczny zestaw) | `systemctl start rider-motion-bridge rider-odometry rider-mapper rider-obstacle rider-navigator` | Startuj w podanej kolejności; upewnij się, że vision/edge-preview dostępne |
| Diagnostyka obrazu | `systemctl start rider-edge-preview.service` lub `rider-ssd-preview.service` | Po testach `systemctl stop ...` by oddać kamerę |

## Minimalne ustawienia unitów (zalecenia do wprowadzenia)

- `Restart=on-failure`, `RestartSec=1`, `StartLimitIntervalSec` + `StartLimitBurst` (większość unitów już ma restart; warto dodać limity).
- `After=network-online.target` oraz `After=dev-video0.device` dla usług kamerowych.
- Services opcjonalne (voice, preview, integracje) – nie włączaj w autostarcie; aktywuj per tryb.
- Autostart utrzymywać w `rider-minimal.target`; `rider-dev.target` tylko gdy potrzebujesz środowiska DEV.

## Propozycje brakujących targetów (do utworzenia, jeśli chcesz)

| Propozycja targetu | Co grupuje | Po co | Status |
| --- | --- | --- | --- |
| `rider-autonomy.target` | motion-bridge, odometry, mapper, obstacle, navigator, vision | Jeden start dla autonomii | Do stworzenia (nie istnieje w repo) |
| `rider-voice.target` | voice-web **lub** voice (wyłączność audio) | Szybkie włączanie sterowania głosem | Do stworzenia |
| `rider-diagnostics.target` | edge-preview, ssd-preview, cam-preview | Sesje diagnostyczne, blokuje kamerę | Do stworzenia |

## Checklist wdrożenia porządku

1. Zweryfikuj, które usługi są faktycznie w `enable` (domyślne WantedBy=multi-user.target); zostaw autostart dla core (`rider-broker`, `rider-api`, `rider-web-bridge`, `rider-vision`, `wifi-unblock`, splash/post-splash).
2. Wyłącz autostart opcyjnych: preview, tracker, obstacle, mapper, navigator, voice*, google-bridge, choreographer, vision-offload, jupyter (chyba że dev box).
3. Dodaj `Conflicts`/lock na kamerę i symetryczne `Conflicts` między `rider-voice-web.service` i `rider-voice.service`.
4. Rozważ stworzenie targetów `rider-autonomy.target` i `rider-diagnostics.target` dla prostych procedur start/stop.
5. W UI przed startem usługi sprawdzaj zasoby; jeśli zajęte, proponuj „Zwolnij zasób → Start”.
6. Dodaj endpoint `/health` w `rider-api` z listą unitów i locków zasobów do widoku diagnostycznego.

---

## Zarządzanie Usługami z Poziomu Rider-PC

Rider-PC może sterować lokalnymi usługami systemd na maszynie, na której jest uruchomiony. Dashboard umożliwia uruchamianie, zatrzymywanie i restartowanie usług bez konieczności logowania się do terminala.

### Konfiguracja Zmiennych Środowiskowych

W pliku `.env` (lub zmiennych środowiskowych) ustaw:

```bash
# Lista jednostek systemd do monitorowania (oddzielona przecinkami)
# Przykład:
MONITORED_SERVICES=rider-pc.service,rider-voice.service,rider-task-queue.service

# Czy używać sudo dla poleceń systemctl (domyślnie: true)
SYSTEMD_USE_SUDO=true
```

### Przygotowanie Systemu Linux (sudoers)

Aby Rider-PC mógł wykonywać polecenia `systemctl` bez hasła, dodaj odpowiednie reguły do sudoers:

1. Otwórz edytor sudoers:
```bash
sudo visudo -f /etc/sudoers.d/rider-pc
```

2. Dodaj reguły (zamień `rider` na użytkownika uruchamiającego aplikację):
```sudoers
# Pozwól użytkownikowi rider zarządzać usługami Rider bez hasła
rider ALL=(root) NOPASSWD: /usr/bin/systemctl start rider-*, \
                           /usr/bin/systemctl stop rider-*, \
                           /usr/bin/systemctl restart rider-*, \
                           /usr/bin/systemctl enable rider-*, \
                           /usr/bin/systemctl disable rider-*
```

3. Ustaw uprawnienia pliku:
```bash
sudo chmod 440 /etc/sudoers.d/rider-pc
```

> **Uwaga bezpieczeństwa**: Przykładowy plik konfiguracyjny znajduje się w `scripts/setup/rider-sudoers.example`. Dostosuj nazwy usług do swojego środowiska.
