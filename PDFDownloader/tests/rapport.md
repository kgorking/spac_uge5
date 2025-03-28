# Test-rapport for PDFDownloader

## Oversigt
- Test resultater
- Kode kvalitet
	- Navngivningskonventioner
		- ensartet, logisk organiseret?
	- Let at forst�/vedligeholde?
	- Fejlh�ndtering
- Testd�kning og evt. forbedringer
- Kommentarer vedr. fejl/ineffektivitet

## Test resultater
### Excel l�ser
- `test_excel_reader` - Funktionen `xlsx_chunk_reader.read_xlsx_in_chunks` kan ikke l�se hele excel filen, den fejler efter chunk nr. 6 med en exception fra pandas.

- `test_excel_reader` - Excel filen �bnes p� ny, hver gang der skal l�ses en del af den. �bningen tager ca. 2 sekunder,
s� for 21K r�kker tager det 42 sekunder at l�se filen.

### Downloader
- `test_corrupted_download` - Korupte filer slettes ikke korrekt, der pr�ves en `unlink` p� en �ben fil.
- `test_needs_user_agent` - Mange hjemmesider kr�ver en user-agent i headeren.
- `test_redirect_with_cookie` - Nogle links peger p� en omdirigerings side, der s�tter en cookie. Hvis den ikke findes n�r destinationen n�es, afvises brugeren.
- `test_zerosize_download` - Filer med st�rrelse 0 skal ikke gemmes.
- `test_ssl_cert_error` - En del links i Excel filerne har ugyldige SSL certifikater, som resulterer i afvisning af downloads. Deaktivering af SSL l�ser dette.
- `test_unsupported_encryption` - PyPDF2 kr�ver `pycryptodome` for at kunne �bne filer med AES kryptering. Hvis det ikke er installeret, fejler �bningen og en gyldig fil slettes.
- `test_url_no_scheme` - En del links mangler `http://` eller `https://` i Excel filerne. Disse links ignorers, selvom de er gyldige.

### Status file
Blev brugt til at blive bekendt med pytest, kan ignoreres.


## Kode kvalitet
### Navngivningskonventioner
- God ensartet navgivning af funktioner og variabler.
- Status- og ui relateret funktioner i `downloader.py` burde ligge i deres egne filer.

### Let at forst�/vedligeholde?
Veldokumenteret kode, og logikken er let at f�lge.

### Fejlh�ndtering


## Testd�kning og evt. forbedringer


## Kommentarer vedr. fejl/ineffektivitet
- status p� enkelte filer, ikke hele m�ngden af downloads.
- Brug af threads til downloads, 60 sekunders timeout.