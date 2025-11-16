# API Sterowania

Punkty końcowe ruchu i sterowania robotem.

## Ścieżka Bazowa
`/api/control`

## Punkty Końcowe

### POST /api/control
Ogólny punkt końcowy komendy sterowania.

**Ciało Żądania:**
```json
{
  "type": "drive|stop|spin",
  "lx": 0.5,      // prędkość liniowa (opcjonalnie, -1.0 do 1.0)
  "az": 0.0,      // prędkość kątowa (opcjonalnie, -1.0 do 1.0)
  "duration": 0.5 // czas trwania w sekundach (opcjonalnie)
}
```

**Odpowiedź:**
```json
{
  "ok": true
}
```

**Przykłady:**

Jazda do przodu:
```bash
curl -X POST http://robot-ip:8080/api/control \
  -H "Content-Type: application/json" \
  -d '{"type": "drive", "lx": 0.5, "az": 0.0}'
```

Stop:
```bash
curl -X POST http://robot-ip:8080/api/control \
  -H "Content-Type: application/json" \
  -d '{"type": "stop"}'
```

Obrót w lewo:
```bash
curl -X POST http://robot-ip:8080/api/control \
  -H "Content-Type: application/json" \
  -d '{"type": "spin", "dir": "left", "speed": 0.3, "duration": 0.5}'
```

---

### POST /api/control/balance
Sterowanie balansem/stabilizacją robota.

**Ciało Żądania:**
```json
{
  "enabled": true  // true aby włączyć, false aby wyłączyć
}
```

**Odpowiedź:**
```json
{
  "ok": true,
  "sent": {
    "enabled": true
  }
}
```

**Temat Magistrali:** `cmd.balance` (TOPIC_MOTION_BALANCE)

**Przykład:**
```bash
curl -X POST http://robot-ip:8080/api/control/balance \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'
```

---

### POST /api/control/height
Sterowanie wysokością/zawieszeniem robota.

**Ciało Żądania:**
```json
{
  "height": 128  // wartość wysokości (0-255)
}
```

**Odpowiedź:**
```json
{
  "ok": true,
  "sent": {
    "height": 128
  }
}
```

**Temat Magistrali:** `cmd.height` (TOPIC_MOTION_HEIGHT)

**Przykład:**
```bash
curl -X POST http://robot-ip:8080/api/control/height \
  -H "Content-Type: application/json" \
  -d '{"height": 150}'
```

---

## Starsze Punkty Końcowe

### POST /api/move
Bezpośrednia komenda ruchu (format starszy).

**Ciało Żądania:**
```json
{
  "vx": 0.5,       // prędkość do przodu/tyłu
  "vy": 0.0,       // prędkość w lewo/prawo (opcjonalnie)
  "yaw": 0.0,      // prędkość obrotu
  "duration": 0.5  // czas trwania w sekundach
}
```

### POST /api/stop
Zatrzymanie ruchu robota (starsze).

### POST /api/preset
Wykonanie predefiniowanego ruchu.

**Ciało Żądania:**
```json
{
  "name": "nazwa_presetu"
}
```

---

## Implementacja

**Moduł:** `services/api_core/control_api.py`

**Publikowane Tematy Magistrali:**
- `cmd.move` - Komendy ruchu
- `cmd.stop` - Komenda stopu
- `cmd.balance` - Sterowanie balansem
- `cmd.height` - Sterowanie wysokością
- `cmd.preset` - Wykonanie presetu

## Zobacz Również

- [API Nawigatora](NAWIGATOR.md) - Nawigacja autonomiczna
- [common/bus.py](../../common/bus.py) - Definicje tematów magistrali
- [Moduł Ruchu](../apps/motion.md) - Dokumentacja systemu ruchu
