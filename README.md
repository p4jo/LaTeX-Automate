# LaTeX-Automate
## automate.ps1
 Automated \input of your project files in alphabetical order.
 
 Exclude files and folders by preceding or following them with '_'



## LaTeX-Beschleunigung mit processPool
Eine Möglichkeit, die Kompilierzeit zu verkürzen, bietet das Skript `processPool.py`. 

Verwendung:
```
    python processPool.py -f filename -o outputFolder
```
Dabei sollte der outputFolder alleine für dieses LaTeX Projekt verwendet werden (sollte aber keine Probleme verursachen, wenn nicht).

Das Programm startet einen Hintergrundprozess, der mehrere LaTeX Prozesse durch die Präambel laufen lässt (und dann pausiert). Sobald dann das Skript noch einmal mit den gleichen Parametern aufgerufen wird, wird ein Prozess zu Ende geführt, wodurch man sich die Zeit in der Präambel spart. 

Caveat: Wenn man etwas in der Präambel, im Index, oder in der .bib Datei verändert, braucht es bis zu 2 Kompiliervorgänge, bis diese Veränderung ankommt. Ein finales Kompilieren sollte also stets per normalem LaTeX durchgeführt werden. Wird die Hauptdatei verändert, so sollten die Hintergrundprozesse erneuert werden und die Änderung durchgehen.
