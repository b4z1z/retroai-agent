; ============================================================================
;  SNAKE.ASM
;  Jeu Snake complet pour DOS (x86 Real Mode)
;  Mode texte 80x25 via acces direct memoire video (B800:0000)
;
;  Assemblage :  tasm snake.asm
;  Linkage    :  tlink snake.obj
;  Execution  :  snake.exe
; ============================================================================

.286
.model small
.stack 200h

; ----------------------------------------------------------------------------
; Constantes
; ----------------------------------------------------------------------------
VID_SEG      equ 0B800h          ; Segment memoire video mode texte
SCR_W        equ 80
SCR_H        equ 25

; Zone de jeu (le serpent meurt s'il touche ces limites)
PLAY_XMIN    equ 2
PLAY_XMAX    equ 77
PLAY_YMIN    equ 2
PLAY_YMAX    equ 22

MAX_LEN      equ 400             ; Taille max du serpent

; Directions
DIR_UP       equ 0
DIR_RIGHT    equ 1
DIR_DOWN     equ 2
DIR_LEFT     equ 3

; Attributs couleur
C_HEAD       equ 0Ah             ; Vert clair
C_BODY       equ 02h             ; Vert
C_APPLE      equ 0Ch             ; Rouge clair
C_WALL       equ 08h             ; Gris
C_TEXT       equ 07h             ; Blanc / gris standard

; Caracteres
CH_HEAD      equ '@'
CH_BODY      equ 'o'
CH_APPLE     equ '*'
CH_WALL      equ '#'

; Scan codes BIOS (touches etendues)
K_UP         equ 48h
K_DOWN       equ 50h
K_LEFT       equ 4Bh
K_RIGHT      equ 4Dh

; ----------------------------------------------------------------------------
; Donnees
; ----------------------------------------------------------------------------
.data
snake_x      db MAX_LEN dup(?)    ; Colonnes du serpent
snake_y      db MAX_LEN dup(?)    ; Lignes du serpent
head         dw ?
tail         dw ?
snake_len    dw ?
direction    db ?
score        dw ?
game_over    db ?
seed         dw ?
apple_x      db ?
apple_y      db ?
speed        db 2                 ; Nombre de ticks timer entre frames

msg_over     db '>>> GAME OVER <<<$'
msg_score    db 'Score: $'
msg_any      db 'Appuyez sur une touche...$'

; ----------------------------------------------------------------------------
; Code
; ----------------------------------------------------------------------------
.code

; --- Point d'entree ---
start:
    mov  ax, @data
    mov  ds, ax

    ; Mode texte 80x25 couleur
    mov  ax, 0003h
    int  10h

    ; ES = segment video B800
    mov  ax, VID_SEG
    mov  es, ax

    call InitGame
    call ClearScreen
    call DrawWalls
    call DrawSnakeFull
    call GenerateApple
    call DrawApple
    call PrintScore

MainLoop:
    cmp  game_over, 1
    je   GameOverState

    call ReadInput
    call UpdateSnake
    cmp  game_over, 1
    je   MainLoop

    call Delay
    jmp  MainLoop

GameOverState:
    call ShowGameOver
    mov  ah, 00h
    int  16h
    mov  ax, 4C00h
    int  21h

; ============================================================================
; PROCEDURES
; ============================================================================

; ----------------------------------------------------------------------------
; InitGame: prepare le serpent et les variables globales
; ----------------------------------------------------------------------------
InitGame proc
    pusha
    mov  head, 2
    mov  tail, 0
    mov  snake_len, 3
    mov  direction, DIR_RIGHT
    mov  score, 0
    mov  game_over, 0

    ; Serpent initial au centre, longueur 3, horizontal vers la droite
    mov  snake_x[0], 38
    mov  snake_y[0], 12
    mov  snake_x[1], 39
    mov  snake_y[1], 12
    mov  snake_x[2], 40
    mov  snake_y[2], 12

    ; Graine aleatoire depuis le timer BIOS (0040:006C)
    push ds
    mov  ax, 0040h
    mov  ds, ax
    mov  ax, ds:[006Ch]
    pop  ds
    mov  seed, ax
    popa
    ret
InitGame endp

; ----------------------------------------------------------------------------
; ClearScreen: efface l'ecran (espaces, attribut 07)
; ----------------------------------------------------------------------------
ClearScreen proc
    pusha
    mov  cx, SCR_W * SCR_H
    mov  di, 0
    mov  ax, 0720h           ; ' ' + attribut 07
    rep  stosw
    popa
    ret
ClearScreen endp

; ----------------------------------------------------------------------------
; PlotChar: ecrit un caractere colore en memoire video
;   Entree: DL = colonne (x), DH = ligne (y)
;           AL = caractere, AH = attribut couleur
; ----------------------------------------------------------------------------
PlotChar proc
    push di
    push bx
    mov  bl, dl            ; sauvegarde x
    mov  bh, dh            ; sauvegarde y
    mov  dl, al            ; DL = caractere
    mov  al, 80
    mul  bh                ; AX = y * 80
    add  al, bl
    adc  ah, 0             ; AX = y*80 + x
    shl  ax, 1             ; *2 (1 word par cellule)
    mov  di, ax
    mov  al, dl            ; AL = caractere
    mov  es:[di], ax       ; ecrit caractere + attribut
    pop  bx
    pop  di
    ret
PlotChar endp

; ----------------------------------------------------------------------------
; DrawWalls: dessine le cadre autour de la zone de jeu
; ----------------------------------------------------------------------------
DrawWalls proc
    pusha
    ; Lignes horizontales (haut et bas)
    mov  cx, PLAY_XMAX
    sub  cx, PLAY_XMIN
    inc  cx
    mov  dl, PLAY_XMIN
    mov  dh, PLAY_YMIN
wall_h:
    push cx
    mov  al, CH_WALL
    mov  ah, C_WALL
    call PlotChar
    mov  dh, PLAY_YMAX
    call PlotChar
    mov  dh, PLAY_YMIN
    inc  dl
    pop  cx
    loop wall_h

    ; Colonnes verticales (gauche et droite, sans redessiner les coins)
    mov  cx, PLAY_YMAX
    sub  cx, PLAY_YMIN
    dec  cx
    jle  wall_done
    mov  dl, PLAY_XMIN
    mov  dh, PLAY_YMIN
    inc  dh
wall_v:
    push cx
    mov  al, CH_WALL
    mov  ah, C_WALL
    call PlotChar
    mov  dl, PLAY_XMAX
    call PlotChar
    mov  dl, PLAY_XMIN
    inc  dh
    pop  cx
    loop wall_v
wall_done:
    popa
    ret
DrawWalls endp

; ----------------------------------------------------------------------------
; DrawSnakeFull: dessine l'integralite du serpent (init + redraw)
; ----------------------------------------------------------------------------
DrawSnakeFull proc
    pusha
    mov  cx, snake_len
    mov  si, tail
dsf_loop:
    push cx
    mov  dl, snake_x[si]
    mov  dh, snake_y[si]
    mov  al, CH_BODY
    mov  ah, C_BODY
    cmp  si, head
    jne  dsf_not_head
    mov  al, CH_HEAD
    mov  ah, C_HEAD
dsf_not_head:
    call PlotChar
    inc  si
    cmp  si, MAX_LEN
    jb   dsf_ok
    xor  si, si
dsf_ok:
    pop  cx
    loop dsf_loop
    popa
    ret
DrawSnakeFull endp

; ----------------------------------------------------------------------------
; IsSnakeAt: teste si la position (DL,DH) touche le corps du serpent
;   Entree: DL = x, DH = y
;   Sortie: ZF = 1 si collision detectee
; ----------------------------------------------------------------------------
IsSnakeAt proc
    push cx
    push si
    mov  cx, snake_len
    mov  si, tail
isa_loop:
    cmp  dl, snake_x[si]
    jne  isa_next
    cmp  dh, snake_y[si]
    je   isa_found
isa_next:
    inc  si
    cmp  si, MAX_LEN
    jb   isa_ok
    xor  si, si
isa_ok:
    loop isa_loop
    ; Pas trouve
    pop  si
    pop  cx
    or   al, 1             ; ZF = 0
    ret
isa_found:
    pop  si
    pop  cx
    xor  ax, ax            ; ZF = 1
    ret
IsSnakeAt endp

; ----------------------------------------------------------------------------
; Rand: generateur pseudo-aleatoire simple (seed = seed*251+127)
;   Sortie: AX = valeur aleatoire 16 bits
; ----------------------------------------------------------------------------
Rand proc
    push bx
    push dx
    mov  ax, seed
    mov  bx, 251
    mul  bx
    add  ax, 127
    mov  seed, ax
    pop  dx
    pop  bx
    ret
Rand endp

; ----------------------------------------------------------------------------
; GenerateApple: choisit une position libre pour la pomme
; ----------------------------------------------------------------------------
GenerateApple proc
    pusha
ga_retry:
    ; X aleatoire
    call Rand
    xor  dx, dx
    mov  bx, PLAY_XMAX
    sub  bx, PLAY_XMIN
    inc  bx
    div  bx                ; DX = reste
    add  dl, PLAY_XMIN
    mov  apple_x, dl

    ; Y aleatoire
    call Rand
    xor  dx, dx
    mov  bx, PLAY_YMAX
    sub  bx, PLAY_YMIN
    inc  bx
    div  bx
    add  dl, PLAY_YMIN
    mov  apple_y, dl

    ; Verifier que la pomme n'est pas sur le serpent
    mov  dl, apple_x
    mov  dh, apple_y
    call IsSnakeAt
    jz   ga_retry

    popa
    ret
GenerateApple endp

; ----------------------------------------------------------------------------
; DrawApple: affiche la pomme a sa position actuelle
; ----------------------------------------------------------------------------
DrawApple proc
    pusha
    mov  dl, apple_x
    mov  dh, apple_y
    mov  al, CH_APPLE
    mov  ah, C_APPLE
    call PlotChar
    popa
    ret
DrawApple endp

; ----------------------------------------------------------------------------
; ReadInput: lecture clavier non bloquante et gestion des directions
;
;   Tous les sauts vers ri_exit et ri_quit utilisent un jmp (near)
;   apres un test inverse court, pour eviter les "relative jump out of range".
; ----------------------------------------------------------------------------
ReadInput proc
    push ax
    push bx
    push cx
    push dx
    push si

    mov  ah, 01h
    int  16h
    jnz  short ri_has_key
    jmp  ri_exit           ; aucune touche pressee
ri_has_key:
    mov  ah, 00h
    int  16h

    cmp  al, 1Bh           ; ESC ?
    jne  short ri_not_esc
    jmp  ri_quit
ri_not_esc:

    mov  bl, direction     ; direction actuelle (pour interdire le demi-tour)

    ; --- Touches etendues (fleches) -> AL = 0 ---
    cmp  al, 0
    jne  ri_try_ascii

    cmp  ah, K_UP
    jne  short ri_not_up
    cmp  bl, DIR_DOWN
    jne  short ri_u1
    jmp  ri_exit
ri_u1:
    mov  direction, DIR_UP
    jmp  ri_exit
ri_not_up:
    cmp  ah, K_DOWN
    jne  short ri_not_down
    cmp  bl, DIR_UP
    jne  short ri_d1
    jmp  ri_exit
ri_d1:
    mov  direction, DIR_DOWN
    jmp  ri_exit
ri_not_down:
    cmp  ah, K_LEFT
    jne  short ri_not_left
    cmp  bl, DIR_RIGHT
    jne  short ri_l1
    jmp  ri_exit
ri_l1:
    mov  direction, DIR_LEFT
    jmp  ri_exit
ri_not_left:
    cmp  ah, K_RIGHT
    jne  ri_exit           ; fleche inconnue -> ignorer
    cmp  bl, DIR_LEFT
    jne  short ri_r1
    jmp  ri_exit
ri_r1:
    mov  direction, DIR_RIGHT
    jmp  ri_exit

    ; --- Touches ASCII (W,A,S,D) ---
ri_try_ascii:
    and  al, 0DFh          ; force majuscule

    cmp  al, 'W'
    jne  short ri_a_not_w
    cmp  bl, DIR_DOWN
    jne  short ri_w1
    jmp  ri_exit
ri_w1:
    mov  direction, DIR_UP
    jmp  ri_exit
ri_a_not_w:
    cmp  al, 'S'
    jne  short ri_a_not_s
    cmp  bl, DIR_UP
    jne  short ri_s1
    jmp  ri_exit
ri_s1:
    mov  direction, DIR_DOWN
    jmp  ri_exit
ri_a_not_s:
    cmp  al, 'A'
    jne  short ri_a_not_a
    cmp  bl, DIR_RIGHT
    jne  short ri_a1
    jmp  ri_exit
ri_a1:
    mov  direction, DIR_LEFT
    jmp  ri_exit
ri_a_not_a:
    cmp  al, 'D'
    jne  ri_exit           ; autre touche -> ignorer
    cmp  bl, DIR_LEFT
    jne  short ri_d2
    jmp  ri_exit
ri_d2:
    mov  direction, DIR_RIGHT
    ; fall through to ri_exit

ri_exit:
    pop  si
    pop  dx
    pop  cx
    pop  bx
    pop  ax
    ret
ri_quit:
    mov  game_over, 1
    pop  si
    pop  dx
    pop  cx
    pop  bx
    pop  ax
    ret
ReadInput endp

; ----------------------------------------------------------------------------
; UpdateSnake: calcule la nouvelle position, verifie collisions,
;              efface la queue ou fait grandir le serpent
; ----------------------------------------------------------------------------
UpdateSnake proc
    pusha

    ; Recuperer position de la tete
    mov  si, head
    mov  dl, snake_x[si]
    mov  dh, snake_y[si]

    ; Calculer nouvelle position selon direction
    cmp  direction, DIR_UP
    jne  us_not_up
    dec  dh
    jmp  us_dir_ok
us_not_up:
    cmp  direction, DIR_DOWN
    jne  us_not_down
    inc  dh
    jmp  us_dir_ok
us_not_down:
    cmp  direction, DIR_LEFT
    jne  us_not_left
    dec  dl
    jmp  us_dir_ok
us_not_left:
    inc  dl
us_dir_ok:

    ; --- Collision avec les murs ---
    cmp  dl, PLAY_XMIN
    jge  short us_xmax_ok
    jmp  us_die
us_xmax_ok:
    cmp  dl, PLAY_XMAX
    jle  short us_ymin_ok
    jmp  us_die
us_ymin_ok:
    cmp  dh, PLAY_YMIN
    jge  short us_ymax_ok
    jmp  us_die
us_ymax_ok:
    cmp  dh, PLAY_YMAX
    jle  short us_body_ok
    jmp  us_die
us_body_ok:
    call IsSnakeAt
    jnz  short us_no_hit
    jmp  us_die
us_no_hit:

    ; Sauvegarde ancienne tete (deviendra corps)
    mov  si, head
    mov  al, snake_x[si]
    mov  bl, snake_y[si]
    push ax                ; ancien x
    push bx                ; ancien y

    ; Avancer la tete dans le buffer circulaire
    inc  si
    cmp  si, MAX_LEN
    jb   us_hok
    xor  si, si
us_hok:
    mov  head, si
    mov  snake_x[si], dl
    mov  snake_y[si], dh

    ; Transformer l'ancienne tete en corps a l'ecran
    pop  bx
    pop  ax
    mov  dl, al
    mov  dh, bl
    mov  al, CH_BODY
    mov  ah, C_BODY
    call PlotChar

    ; Verifier si pomme mangee
    mov  si, head
    mov  dl, snake_x[si]
    mov  dh, snake_y[si]
    cmp  dl, apple_x
    jne  us_no_apple
    cmp  dh, apple_y
    jne  us_no_apple

    ; --- Pomme mangee ---
    inc  score
    inc  snake_len
    call GenerateApple
    call DrawApple
    call PrintScore
    jmp  us_draw_head

us_no_apple:
    ; --- Deplacer la queue (effacer l'ancienne) ---
    mov  si, tail
    mov  dl, snake_x[si]
    mov  dh, snake_y[si]
    mov  al, ' '
    mov  ah, C_TEXT
    call PlotChar
    inc  si
    cmp  si, MAX_LEN
    jb   us_tok
    xor  si, si
us_tok:
    mov  tail, si

us_draw_head:
    ; Dessiner la nouvelle tete
    mov  si, head
    mov  dl, snake_x[si]
    mov  dh, snake_y[si]
    mov  al, CH_HEAD
    mov  ah, C_HEAD
    call PlotChar

    popa
    ret

us_die:
    mov  game_over, 1
    popa
    ret
UpdateSnake endp

; ----------------------------------------------------------------------------
; PrintUInt: affiche un entier 16 bits non signe en decimal (INT 21h)
;   Entree: AX = nombre
; ----------------------------------------------------------------------------
PrintUInt proc
    pusha
    mov  cx, 10
    mov  bx, ax
    cmp  ax, 0
    jne  pui_convert
    mov  dl, '0'
    mov  ah, 02h
    int  21h
    jmp  pui_done
pui_convert:
    mov  bp, sp
pui_loop:
    xor  dx, dx
    div  cx
    push dx
    cmp  ax, 0
    jne  pui_loop
pui_print:
    pop  dx
    add  dl, '0'
    mov  ah, 02h
    int  21h
    cmp  sp, bp
    jne  pui_print
pui_done:
    popa
    ret
PrintUInt endp

; ----------------------------------------------------------------------------
; PrintScore: affiche le score en haut a gauche de l'ecran
; ----------------------------------------------------------------------------
PrintScore proc
    pusha
    ; Positionner le curseur
    mov  dh, 0
    mov  dl, 0
    mov  bh, 0
    mov  ah, 02h
    int  10h

    ; Texte "Score: "
    mov  ah, 09h
    lea  dx, msg_score
    int  21h

    ; Valeur numerique
    mov  ax, score
    call PrintUInt

    popa
    ret
PrintScore endp

; ----------------------------------------------------------------------------
; ShowGameOver: affiche le message de fin au centre de l'ecran
; ----------------------------------------------------------------------------
ShowGameOver proc
    pusha
    ; Ligne centrale
    mov  dh, 12
    mov  dl, 28
    mov  bh, 0
    mov  ah, 02h
    int  10h

    mov  ah, 09h
    lea  dx, msg_over
    int  21h

    ; Afficher le score sur la meme ligne
    mov  ax, score
    call PrintUInt

    ; Message secondaire
    mov  dh, 14
    mov  dl, 24
    mov  ah, 02h
    int  10h
    lea  dx, msg_any
    mov  ah, 09h
    int  21h

    popa
    ret
ShowGameOver endp

; ----------------------------------------------------------------------------
; Delay: attend un nombre de ticks du timer BIOS (18.2 Hz)
; ----------------------------------------------------------------------------
Delay proc
    pusha
    push es
    mov  ax, 0040h
    mov  es, ax
    mov  bx, es:[006Ch]
delay_loop:
    mov  ax, es:[006Ch]
    sub  ax, bx
    cmp  al, speed
    jb   delay_loop
    pop  es
    popa
    ret
Delay endp

; --- Fin du programme ---
end start
