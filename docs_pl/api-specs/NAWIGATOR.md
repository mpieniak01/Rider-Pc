# API Nawigatora

Punkty końcowe sterowania nawigacją autonomiczną (tryb Rekonesans).

## Ścieżka Bazowa
`/api/navigator`

## Przegląd

API Nawigatora steruje autonomicznym trybem Rekonesans (zwiadu), który obejmuje:
- **Etap 1**: Reaktywne unikanie przeszkód ze strategiami STOP i AVOID
- **Etap 4**: Nawigacja powrotu do domu z wyszukiwaniem ścieżki A*

## Punkty Końcowe

### POST /api/navigator/start
Rozpoczęcie nawigacji autonomicznej w trybie Rekonesans.

**Ciało Żądania:**
```json
{
  "strategy": "STOP"  // lub "AVOID"
}
```

**Strategie:**
- `STOP` - Natychmiastowe zatrzymanie gdy wykryto przeszkodę (tryb bezpieczny)
- `AVOID` - Skręt w prawo i kontynuacja gdy wykryto przeszkodę (tryb eksploracji)

**Odpowiedź:**
```json
{
  "ok": true,
  "action": "start",
  "strategy": "STOP"
}
```

**Temat Magistrali:** `navigator.control`

**Przykład:**
```bash
curl -X POST http://robot-ip:8080/api/navigator/start \
  -H "Content-Type: application/json" \
  -d '{"strategy": "AVOID"}'
```

---

### POST /api/navigator/stop
Zatrzymanie nawigacji autonomicznej.

**Ciało Żądania:** (puste lub `{}`)

**Odpowiedź:**
```json
{
  "ok": true,
  "action": "stop"
}
```

**Temat Magistrali:** `navigator.control`

**Przykład:**
```bash
curl -X POST http://robot-ip:8080/api/navigator/stop
```

---

### POST /api/navigator/config
Aktualizacja konfiguracji nawigatora w czasie działania.

**Ciało Żądania:**
```json
{
  "strategy": "AVOID",     // opcjonalnie: "STOP" lub "AVOID"
  "fwd_speed": 0.4,        // opcjonalnie: prędkość do przodu (0.0-1.0)
  "turn_speed": 0.5,       // opcjonalnie: prędkość obrotu (0.0-1.0)
  "turn_duration": 0.6,    // opcjonalnie: czas trwania obrotu (sekundy)
  "cooldown": 1.0          // opcjonalnie: czas ochłodzenia po uniknięciu (sekundy)
}
```

**Odpowiedź:**
```json
{
  "ok": true,
  "action": "config",
  "config": {
    "strategy": "AVOID",
    "fwd_speed": 0.4,
    "turn_speed": 0.5
  }
}
```

**Temat Magistrali:** `navigator.control`

**Przykład:**
```bash
curl -X POST http://robot-ip:8080/api/navigator/config \
  -H "Content-Type: application/json" \
  -d '{"strategy": "AVOID", "fwd_speed": 0.4}'
```

---

### GET /api/navigator/status
Pobieranie informacji o statusie nawigatora.

**Odpowiedź:**
```json
{
  "ok": true,
  "note": "Punkt końcowy statusu - subskrybuj temat navigator.state dla aktualizacji w czasie rzeczywistym",
  "topic": "navigator.state"
}
```

**Uwaga:** Dla aktualizacji statusu w czasie rzeczywistym, subskrybuj temat magistrali `navigator.state`.

---

### POST /api/navigator/return_home
**NOWE w Etapie 4**: Uruchomienie nawigacji autonomicznej z powrotem do pozycji startowej.

**Ciało Żądania:** (puste lub `{}`)

**Odpowiedź:**
```json
{
  "ok": true,
  "action": "return_home"
}
```

**Zachowanie:**
1. Zatrzymuje bieżącą aktywność eksploracji
2. Żąda mapy siatki zajętości od mappera
3. Oblicza optymalną ścieżkę używając algorytmu A*
4. Podąża punktami węzłowymi aby wrócić do punktu początkowego (0, 0)
5. Zatrzymuje się jeśli wykryto przeszkodę podczas powrotu

**Tematy Magistrali:**
- Publikuje: `navigator.return_home.start`
- Publikuje: `navigator.map.request` (żąda mapy od mappera)
- Subskrybuje: `mapper.map.data` (odbiera mapę)
- Subskrybuje: `robot.pose` (bieżąca pozycja z odometrii)

**Przykład:**
```bash
curl -X POST http://robot-ip:8080/api/navigator/return_home
```

**Wymagania Wstępne:**
- `rider-odometry.service` musi działać (do śledzenia pozycji)
- `rider-mapper.service` musi działać (do danych mapy)
- Robot musi zbadać pewien obszar (mapa musi istnieć)

---

## Stany Nawigatora

Nawigator publikuje aktualizacje stanu na temacie magistrali `navigator.state`:

```json
{
  "active": true,
  "state": "exploring",
  "strategy": "AVOID",
  "obstacle_present": false,
  "ts": 1234567890.123
}
```

**Stany:**
- `idle` - Nawigator nieaktywny
- `exploring` - Aktywna eksploracja, ruch do przodu
- `avoiding` - Obracanie się aby uniknąć przeszkody (strategia AVOID)
- `stopped` - Zatrzymany z powodu przeszkody (strategia STOP) lub ręcznego stopu
- `returning_home` - Nawigacja z powrotem do pozycji startowej
- `path_blocked` - Wykryto przeszkodę podczas powrotu do domu

---

## Zmienne Środowiskowe Konfiguracji

Domyślna konfiguracja może być ustawiona przez zmienne środowiskowe:

```bash
NAVIGATOR_LOG_LEVEL=INFO          # Poziom logowania
NAVIGATOR_STRATEGY=STOP           # Domyślna strategia
NAVIGATOR_FWD_SPEED=0.3          # Prędkość do przodu (0.0-1.0)
NAVIGATOR_TURN_SPEED=0.4         # Prędkość obrotu (0.0-1.0)
NAVIGATOR_TURN_DURATION=0.5      # Czas trwania obrotu (sekundy)
NAVIGATOR_COOLDOWN=1.0           # Czas ochłodzenia po uniknięciu (sekundy)
NAVIGATOR_AUTO_START=0           # Auto-start przy uruchomieniu (0=nie, 1=tak)

# Śledzenie Ścieżki (Powrót do Domu)
NAVIGATOR_WAYPOINT_TOLERANCE=0.15  # Odległość do punktu węzłowego (metry)
NAVIGATOR_ANGLE_TOLERANCE=0.2      # Tolerancja kąta (radiany ~11°)
NAVIGATOR_GOAL_TOLERANCE=0.1       # Końcowa odległość do celu (metry)
```

---

## Implementacja

**Moduł:** `services/api_core/navigator_api.py`  
**Rdzeń Nawigatora:** `apps/navigator/main.py`  
**Wyszukiwanie Ścieżki:** `apps/navigator/pathfinding.py`

**Tematy Magistrali:**
- **Publikowane:**
  - `navigator.control` - Komendy sterowania
  - `navigator.state` - Aktualizacje stanu
  - `navigator.map.request` - Żądania mapy
  - `navigator.return_home.start` - Wyzwalacz powrotu do domu
  - `motion` - Komendy ruchu

- **Subskrybowane:**
  - `vision.obstacle` - Wykrywanie przeszkód
  - `robot.pose` - Pozycja robota (odometria)
  - `mapper.map.data` - Mapa siatki zajętości

---

## Zależności

**Wymagane Usługi:**
- `rider-broker.service` - Broker komunikatów ZMQ
- `rider-vision.service` - Wykrywanie przeszkód
- `rider-obstacle.service` - Detektor przeszkód ROI

**Opcjonalne Usługi (dla pełnej funkcjonalności Rekonesans):**
- `rider-odometry.service` - Śledzenie pozycji (Etap 2)
- `rider-mapper.service` - Mapowanie SLAM (Etap 3)

---

## Interfejs Webowy

Nawigator jest sterowany przez interfejs webowy pod adresem `http://robot-ip:8080/control.html`:

**Kontrolki:**
- Checkbox do włączania/wyłączania trybu Rekonesans
- Selektor strategii (STOP / AVOID)
- Przycisk "🏠 Powrót do Bazy" (pojawia się gdy aktywny)
- Wskaźnik statusu w czasie rzeczywistym pokazujący bieżący stan

---

## Zobacz Również

- [Dokumentacja Modułu Nawigatora](https://github.com/mpieniak01/Rider-Pi/blob/main/docs/apps/navigator.md) - Szczegółowa dokumentacja modułu
- [Moduł Odometrii](https://github.com/mpieniak01/Rider-Pi/blob/main/docs/apps/odometry.md) - Śledzenie pozycji
- [Moduł Mappera](https://github.com/mpieniak01/Rider-Pi/blob/main/docs/apps/mapper.md) - Mapowanie SLAM
- [Moduł Wizji](https://github.com/mpieniak01/Rider-Pi/blob/main/docs/apps/vision.md) - Wykrywanie przeszkód
- [API Sterowania](STEROWANIE.md) - Podstawowe sterowanie ruchem
