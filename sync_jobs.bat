@echo off
set "SRC=W:\u\HTML"
set "DEST=C:\Users\mlieberwirt\Desktop\HTM_zu_SQLite\daten"

:loop
echo [%date% %time%] Synchronisiere Dateien von %SRC% nach %DEST%
robocopy "%SRC%" "%DEST%" /E /MIR /NFL /NDL /NJH /NJS /R:1 /W:1
timeout /t 60 >nul
goto loop
