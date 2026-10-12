# Sterowanie Rider-PC: ustawienia i odczyty

Rider-Pi przechowuje kalibrację i profile oraz realizuje mapowanie kierunków,
wygładzanie, zastępowanie poleceń i watchdog sprzętu. Rider-PC przekazuje zamiar
operatora. Nie zapisuje osobnej kalibracji robota.

## Panel

Sterowanie i Kalibracja odczytują kontrakt v2 z
`GET /api/calibration/controls`: jednostki, przeliczniki wyświetlania, zakresy,
tryby ruchu, profile i rewizję. Zapis oraz operacje profili trafiają do tego samego
punktu na Pi.

Zmiana pola tworzy szkic. Przycisk zapisu wymaga właściwej rewizji; konflikt
wymaga sprawdzenia aktualnych wartości. Zmiana suwaka nie wyzwala ruchu.

Kliknięcie wysyła impuls; przytrzymanie odnawia polecenie według kontraktu Pi;
puszczenie uruchamia wyhamowanie, pozostawiając uzbrojenie. Wysyłane są kierunek,
tryb, device_settings i rewizja. PC nie przelicza kierunku na vx/yaw i nie
realizuje drugiej rampy.

Istnieje najwyżej jedno żądanie gestu w toku i jeden najnowszy zamiar. STOP
natychmiast kasuje odnowienia. Nie wymaga negocjacji kontraktu ani zegara.
Utrata fokusu lub ukrycie karty kończy gest. Uzbrojenie pozostaje decyzją
operatora; zgoda testów jest oddzielna.

Proxy zachowuje generację, sekwencję, znacznik czasu i TTL. Przed ruchem sprawdza
świeże bezpieczeństwo; ostatecznie decyduje Pi. Wysłanie żądania i przyjęcie
przez SDK nie są potwierdzeniem fizycznego wykonania.

Wysokość, balans i figury korzystają z tych samych poleceń i możliwości co panel
Pi. Kalibracja ma kompaktowe zarządzanie profilami i wspólne nastawy.

## Odczyty i obciążenie

Równoczesne identyczne odczyty w adapterze PC współdzielą transfer. Odbiorcy
otrzymują osobne kopie i oryginalne czasy źródłowe. Zakończone odczyty
bezpieczeństwa nie są cache'owane. Zapis unieważnia współdzielenie wcześniejszych
odczytów; polecenia nie są łączone ani odtwarzane.

Katalog ma wspólny odczyt przeglądarkowy przez sekundę i ograniczony czas
potwierdzenia zgodności kontraktu. Lokalne funkcje PC nie wymagają negocjacji
kontraktu robota. STOP, rozbrojenie i ESTOP pomijają tę negocjację.

Przegląd: telemetria 1 s, system Pi 2 s, wizja 2 s przy aktywnej kamerze,
katalog/metryki i zasoby PC 10 s. Nieaktywna lub nieznana kamera powoduje jeden
odczyt metadanych i wstrzymanie cyklicznych zapytań o przeszkody.
Wykres Pi korzysta z hist_ts i hist_cpu_peak źródłowego próbkowania, pokazuje
piki i przerwy bez dodatkowego pomiaru CPU. Stan LCD obsługuje potwierdzony
odczyt GPIO podświetlenia i wyświetla ON/OFF.

Odczyt bezpieczeństwa REST oraz BUS/SSE nadal współistnieją. Nie zastępujemy
uzgadniania zegara cache'owanym czasem BUS. Docelowy zbieracz zależny od
subskrypcji musi zachować gwarancje zegara i TTL.

## Sprawdzanie

Uzbrojenie, strzałki, przytrzymanie, STOP i zapis nastaw sprawdzamy w izolowanych
mockach. Ruch fizyczny wymaga osobnej decyzji operatora. Na działającym robocie
można odczytowo porównać rewizję, jednostki i potwierdzenie wykonawcy.
