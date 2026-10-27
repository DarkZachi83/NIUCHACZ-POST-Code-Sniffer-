# POST code sources / Źródła kodów POST

Descriptions are written in our own words (EN + PL). The `confidence` field of each entry says how much to trust it.
Opisy są napisane własnymi słowami (EN + PL). Pole `confidence` przy każdym wpisie mówi, na ile można mu ufać.

| File / plik | BIOS | Source / źródło | `confidence` |
|---|---|---|---|
| `ami_1990.json` | AMI, core before 4/9/1990 (286) | AMI POST checkpoint tables by BIOS core date – [files.retropc.se](https://files.retropc.se/drivers_1/EMO/BIOS/AMI-POST.html) | `community_list` |
| `ami_1991.json` | AMI, core 4/9/1990 – 2/15/1991 | same | `community_list` |
| `ami_1992.json` | AMI, core from 2/15/1991 (also after 6/6/1992 – identical table) | same | `community_list` |
| `ami_win.json` | AMI WinBIOS | [dosdays.co.uk – AMI BIOS](https://dosdays.co.uk/topics/bios_ami.php) (WinBIOS column, no source given) on top of `ami_1992` | `community_list` |
| `ami.json` | AMIBIOS8 | *AMIBIOS8 Check Point and Beep Code List v2.0* (AMI) + observations on ASRock 775V88 | `ami_docs`, `observed` |
| `award_45.json` | Award 4.50 / 4.51 | Winford Engineering PST44 POST card manual – [winford.com](https://www.winford.com/download/pst44manual.pdf) | `postcard_docs` |
| `award.json` | Award 4.51PG / 6.00PG | Gigabyte *GA-G1975X POST Code Definition* (Award), 2005 – [gigabyte.com](https://download1.gigabyte.com/Files/Manual/motherboard_manual_ga-g1975x_post-code.pdf) | `oem_docs` |
| `phoenix.json` | PhoenixBIOS 4.0 Release 6.x | *PhoenixBIOS 4.0 User's Manual* (2000), ch. 4 – [bitsavers](https://ftp.mirrorservice.org/sites/www.bitsavers.org/pdf/phoenix/PhoenixBIOS_4.0_Users_Manual_2000.pdf) | `vendor_docs` |

**Beep codes / sygnały dźwiękowe:** AMI – [ASRock FAQ](https://www.asrock.com/support/faq.pl.asp?id=2) (`oem_docs`);
Phoenix – the manual above (`vendor_docs`); Award – [pitt.edu](https://sites.pitt.edu/~hunter3/ComputerHelp/BIOScodes.htm) (`community_list`, Award documents almost none).

**Not yet / jeszcze brak:** AMI Hi-Flex (the 1993 *Hi-Flex AMIBIOS Technical Reference* on bitsavers has the table,
but only as a scan), Award 3.x and earlier, Phoenix before 4.0, IBM/Compaq/Dell own BIOSes, XT-class machines
(most XT BIOSes write no POST codes to port 80h).

`fault` / `check` for the older BIOSes are general hints by kind of stage (memory, keyboard controller, video…),
not from the sources. / Pola `fault` / `check` dla starszych BIOS-ów to ogólne podpowiedzi według rodzaju etapu,
nie z dokumentów źródłowych.
