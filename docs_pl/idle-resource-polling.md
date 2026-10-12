# Odczyty nieaktywnych zasobów

Rider-PC ma jeden harmonogram na klucz obserwacji. Stan i system są sprawdzane
co 2 sekundy, kondycja co 5 sekund, a metryki aplikacji/BUS co 10 sekund.
Jawne odczyty telemetrii zachowują krótki budżet świeżości. Pełna diagnostyka
właścicieli zasobów jest pobierana na żądanie, nie stale w tle. Wszystkie
odczyty danego zasobu korzystają z tego samego cache i żądania w toku.
Akcje zadań/zasobów unieważniają odczyty, również wcześniejsze żądania w toku.

Stan kamery obecny już w state/health Pi decyduje o pobieraniu klatek w tle.
OFF, niedostępność i stan nieznany zatrzymują pobieranie obrazów oraz odpytywanie
wizji w tle. ON wznawia odczyty wizji. Jawne zapytanie o metadane nadal pozwala
obejrzeć informacje o archiwalnych plikach. Bieżący obraz przy potwierdzonym OFF
zwraca lokalnie 404; jawne archiwum nadal pobieramy z Pi.
Tło oraz GET/HEAD współdzielą transfer klatki przez 0,8 sekundy, zachowując
nagłówki i czasy źródłowe. Po błędzie tło ponawia transfer po 5 sekundach.
Odczyty nigdy nie uruchamiają zasobów ani aktuatorów.

Pi współdzieli skany właścicieli urządzeń między endpointami. Potwierdzony
wolny zasób i nieudany odczyt są przechowywane przez 5 sekund, zajęty zasób
przez 3 sekundy. Akcje zasobów unieważniają cache. Faktyczne odzyskiwanie
zasobu nadal pobiera aktualną listę właścicieli bezpośrednio przed działaniem.
