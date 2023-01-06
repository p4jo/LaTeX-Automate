sudo cp /home/johannesh/repos/LaTeX-privat/Automate/JHKeyboard.xkb /usr/share/X11/xkb/symbols/LayoutJH
# cp ./Automate/JHKeyboard ~/.config/xkb/symbols/
# cp ./Automate/evdev.xml ~/.config/xkb/rules/
# setxkbmap -layout JHKeyboard -variant JHGerman -v

# just once: 
# sudo ln -s ./Automate/JHKeyboard.xkb /usr/share/X11/xkb/symbols/JHKeyboard
sudo ln -s /home/johannesh/repos/LaTeX-privat/Automate/.XCompose ~/.XCompose
ibus restart