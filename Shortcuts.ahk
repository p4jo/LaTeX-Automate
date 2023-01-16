#SingleInstance force
#NoEnv  ; Recommended for performance and compatibility with future AutoHotkey releases.
#Warn  ; Enable warnings to assist with detecting common errors.
SendMode Input  ; Recommended for new scripts due to its superior speed and reliability.
SetTitleMatchMode 2

GroupAdd, Programmieren, Visual Studio,,, LaTeX
GroupAdd, Programmieren, .py
GroupAdd, Programmieren, .ts
GroupAdd, Programmieren, .js
GroupAdd, Programmieren, .ps1
GroupAdd, Programmieren, Unity

GroupAdd, LaTeX, .tex
GroupAdd, LaTeX, .cls
GroupAdd, LaTeX, .sty
GroupAdd, LaTeX, LaTeX,,, .ahk ; LaTeX im Titel, aber nicht .ahk

; +^!F12::Suspend  ;  Press it again to resume.

; ~^!A::
~^+^::
	Suspend, On
	Sleep 10000
	Suspend, Off
return


; Extrazeichen auf AltGr und Hotstrings

^!r::
	Send ρ
return

^!U::
	Send θ
return
+^!U::
	Send Θ
return

^!b::
	Send β
return

^!f::
	Send φ
return
^!a::
	Send α
return

^!n::
	Send ν
return

^!m::
	Send μ
return

^!l::
	Send λ
return
+^!l::
	Send Λ
return

^!t::
	Send τ
return

^!p::
	Send π
return
+^!p::
	Send Π
return

^!v::
	Send ω
return
^!c::
	Send ψ
return

^!d::
	; Send Δ ; Das ist der Buchstabe Δ auf der griechischen Tastatur
	Send ∆ ; Das ist ein aufrechtes Dreieck für ∆x oder ∆T (U+2206). Das wird normalerweise im AP oder so verwendet, aber auch für den Laplace-Operator. Normale (Variablen) Δ sollten kursiv sein.
return

#n::
	Send ∇
return

^!ü::
	Send ∞
return


#,::[

#.::]

^!,::
	Send {{}
return
 
^!.::
	Send {}}
return 

^!-::
	; Send % "\cdot "
	Send % "·"
return
#-::
	Send % "×"
return

#t::
	Send % "\tilde "
return

$´::
	Send \
return
`::
	SendInput % Chr(0x60)
	; SendEvent {Space}
	; Sleep 2000
	; SendEvent {Space}{BackSpace}
return
^!´::
	SendEvent ´
return

^!w:: ; Verwende #F7 zuerst, s. u.
	Send, ^9 ; Griechische Tastatur
	Sleep, 800
	Send ^8	; Deutsche Tastatur
return

#0::
	Send % "≡ "
return

; #If WinActive("ahk_group Programmieren") or WinActive("ahk_group LaTeX")
	$7::
		Send /
	return
	$8::
		Send (
	return
	$9::
		Send )
	return
; #If

#IfWinNotActive ahk_group Programmieren

	NumpadDiv::
		Send ÷
	return

	::==>::
		Send % "⟹ "
	::=>::
		Send % "⇒ "
	return
	::<==::
		Send % "⟸ "
	return
	::<=>::
		Send % "⇔ "
	return

	::-->::
		Send % "⟶ "
	return
	::->::
		Send % "↦"
	return
	::<- ::
		Send % "↤"
	return
	::<--::
		Send % "⟵ "
	return
	::i->::
		Send % "↪ "
	return
	::->>::
		Send % "↠ "
	return
	::<=::
		Send % "≤ "
	return
	::>=::
		Send % "≥ "
	return
	::!=:: 
		Send % "≠ "
	return
	::=d::
		Send % "≝ "
	return
	::=^::
		Send % "≙ "
	return

	::>m::
		Send % "⊇ "
	return
	::<m::
		Send % "⊆ "
	return

	::<e::
		Send % "∈ "
	return
	::>e::
		Send % "∋ "
	return
	::<i::
		Send % "∊ "
	return
	::>i::
		Send % "∍ "
	return

	::<<::
		Send % "≪ "
	return

	::+-::
		Send ±
	return
	::-+::
		Send ∓
	return

	:::=:: 
		Send ≔
	return

	::=: ::
		Send % "≕ "
	return

	::rrr::
		Send ℝ
	return
#IfWinNotActive


#If WinActive("ahk_group LaTeX") and not WinActive("ahk_group Programmieren")

	^::
		Send % "{^} " ; Sonst erwartet es ein Zeichen und z.B. ^u zu tippen ergibt û
	return

	; ^!^::
	; 	Send ^
	; return
	
	#b::
		Send % "\numberset "
	return
	
	#d::
		Send \Def{{}
	return

	"::
		Send \enquote{{}
	return

	#a::
		Send \autoref{{}
	return
	
	#2::
		Send % """" ; Escape character für " ist ""
	return
		
	#::
		Send \frac
	return
	
	+7::
		Send % "\over "
	return

	##::
		Send \sfrac
	return

	^!#::
		Send {#}
	return 

	^!s:: 
		Send % "\sub{"
	return

	#+::
		Send % "∝ " 
	return

	; AppsKey & <::
	; 	if(GetKeyState("Shift", "P"))
	; 		Send % "\right\rangle "
	; 	else
	; 		Send % "\left\langle "
	; return

	#<::
		; Send % "\left\langle "
		Send % "\Qty<>{Left}"
	return
	; #+<::
	; 	Send % "\right\rangle "
	; return

	^!g::
		Send \Gleichung
	return

	^!h::
		Send \hquer
	return

	$3::
	$4::
		Send $
	return
	^!3::
		Send 3
	return
	^!4::
		Send 4
	return
	; $5::
	; 	Send `%
	; return
	^!5::
		Send 5
	return
	$6::
		Send &
	return
	^!6::
		Send 6
	return
	
	$+8::
		Send \qty(
	return
	; NumpadSub::BackSpace
	^!+,::
		Send \qty{{}
	return
	#+,::
		Send \qty[
	return
	
	^!+7::
		Send \qty{{}
	return
	^!+8::
		Send \qty[
	return
	^!+9::
		Send ]
	return
	^!+0::
		Send {}}
	return

	^!ö::
		Send ￭
	return

#IfWinActive

	

#IfWinActive Cyanide
	~XButton2::Right
#IfWinActive

#IfWinActive .ahk
	~^s:: 
		Sleep, 90
		Reload
	return
#IfWinActive

#IfWinActive .py
	^!s:: 
		Send % "self."
	return
#IfWinActive

#If WinActive("Microsoft Visual Studio") or WinActive("ahk_exe pycharm64.exe")
	XButton1::!Left
	XButton2::!Right
#IfWinActive

#F8::
    Reload
return

; Zoomen via Drücken und Drehen des Mausrads
~MButton & WheelDown::
	Send {Ctrl Down}{WheelDown}{Ctrl Up}
	return

~MButton & WheelUp::
	Send {Ctrl Down}{WheelUp}{Ctrl Up}
	return
	
MButton:: MButton

 

; EMOJIS
Browser_Favorites::
	Send {LWin down}.{LWin Up} 
return

; OLD WIN 10 SHORTCUTS

; ; Standby shortcuts
; #W::
; 	Sleep(False)
; return

; #+W::
; 	Sleep(True)
; return

; Sleep(Hibernate){
; 	SetKeyDelay 40, 20
; 	KeyWait LWin
; 	SendEvent {LWin}
; 	Sleep 500
; 	SendEvent {Tab}{Down 6}{Space}
; 	Sleep 100
; 	if (Hibernate){
; 		SendEvent {Down}
; 	}
; 	SendEvent {Space}
; 	SetKeyDelay
; }

; #Y::
; 	SetSoundOutput(False)
; return

; #X::
; 	SetSoundOutput(True)
; return

; SetSoundOutput(Upmost){
; 	SetKeyDelay 120, 20
; 	KeyWait LWin
; 	SendEvent {LWin Down}b{LWin Up}
; 	Sleep 200
; 	SendEvent {Down}{Space}
; 	WinWaitActive, Lautstärkeregelung,, 0.5
; 	if (ErrorLevel == 1){
; 		return
; 	}
; 	SendEvent {Tab}{Space}
; 	Sleep 300
	
; 	if (Upmost){
; 		SendEvent {Up 3}{Space}
; 	}
; 	else{
; 		SendEvent {Down 3}{Space}
; 	}
; 	Sleep 400
; 	SendEvent {Escape}
; }
; ; Fenster im Vordergrund halten
; #^::
; 	WinSet, AlwaysOnTop, Toggle, A
; return
; ; Setze Strg+1 bzw. 2 als Shortcut für Eingabesprachen
; #F7::
; 	SendMode, Event
; 	KeyWait, RWin
; 	KeyWait, LWin
; 	KeyWait, F7
; 	Send, #i
; 	WinWaitActive, Einstellung
; 		Sleep, 100

; 		Send {Alt Down}{F4}{Alt Up} ; Um danach die Einstellungen auf der Hauptseite zu starten
; 	Sleep, 100
; 	Send, #i
; 	WinWaitActive, Einstellung
; 		Sleep, 1500

; 		Send, erweiterte{Space}tast{Enter}

; 		Sleep, 500

; 		Send {Enter} ; Erweiterte Tastatureinstellungen
; 		Sleep 200

; 		Send, {Tab}
; 		Sleep 100
; 		Send, {Tab}
; 		Sleep 100
; 		Send, {Tab}
; 		Sleep, 100 		
; 		Send, {Enter} ; Tastenkombination für Eingabesprachen

; 		WinWaitActive, Textdienste
; 		Sleep, 150

; 			Send, {Tab}
; 			Sleep, 100

; 			Send, {Down}
; 			Sleep, 100

; 			Send, {Alt Down}n{Alt Up} ; Tastenkombination für Deutsche Tastatur eingeben
; 			Sleep, 200

; 				Send, {Space}{Tab}{Tab}{Down 8} ; Anschalten und Tab + 8
; 				Sleep, 100

; 				Send {Enter} ; Fertig
; 				Sleep, 200

; 			Send {Down}{Down}
; 			Sleep, 100

; 			Send {Alt Down}n{Alt Up} ; Tastenkombination für griechische Tastatur eingeben
; 			Sleep, 200

; 				Send {Space}{Tab}{Tab}{Down 8}  ; Anschalten und Tab + 9
; 				Sleep, 200

; 				Send {Enter} ;fertig
; 				Sleep, 117

; 			Send {Alt Down}b{Alt Up} ; Übernehmen

; 			WinWaitActive, Textdienste
; 			Send {Alt Down}{F4}{Alt Up} ; Pop-up-Fenster schließen

; 		WinWaitActive, Einstellung
; 		Send {Alt Down}{F4}{Alt Up}

; 	SendMode Input
; return

