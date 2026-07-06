pile segment stack
    db 512 dup(0)
pile ends

data segment
    pal_g_y     dw 80
    pal_d_y     dw 80
    old_g_y     dw 80
    old_d_y     dw 80

    balle_x     dw 160
    balle_y     dw 100
    old_b_x     dw 160
    old_b_y     dw 100
    vbx         dw 2
    vby         dw 1
    speed       dw 2

    px          dw 0
    py          dw 0
    larg        dw 0
    haut        dw 0
    couleur     db 0

    score_g     db 0
    score_d     db 0
    gagnant     db 0
    quit_flag   db 0

    C_P1        equ 9
    C_P2        equ 12
    C_BALL      equ 14
    C_NET       equ 8
    C_BG        equ 0
    PAD_W       equ 6
    PAD_H       equ 40
    BALL_S      equ 4
    SCR_MAX     equ 5


    msg_title   db 'PONG EXTREME$'
    msg_sub     db 'J1: Z/S     J2: FLECHES$'
    msg_start   db 'APPUYEZ SUR UNE TOUCHE$'
    msg_p1      db 'J1:$'
    msg_p2      db 'J2:$'
    msg_go      db 'GAME OVER$'
    msg_w1      db 'VICTOIRE JOUEUR $'
    msg_replay  db 'R: REJOUER  ESC: QUITTER$'
data ends

code segment
assume cs:code, ss:pile, ds:data

draw_rect proc near
    push ax
    push cx
    push dx
    push di
    push si
    push es

    mov ax, 0A000h
    mov es, ax

    mov ax, [py]
    mov bx, 320
    mul bx
    add ax, [px]
    mov di, ax

    mov al, [couleur]
    mov cx, [larg]
    mov si, [haut]
    cmp si, 0
    je dr_end

dr_row:
    push di
    rep stosb
    pop di
    add di, 320
    dec si
    jnz dr_row

dr_end:
    pop es
    pop si
    pop di
    pop dx
    pop cx
    pop ax
    ret
draw_rect endp

clear_screen proc near
    mov [px], 0
    mov [py], 0
    mov [larg], 320
    mov [haut], 200
    mov [couleur], C_BG
    call draw_rect
    ret
clear_screen endp

draw_net proc near
    push cx
    mov [px], 158
    mov [larg], 4
    mov [haut], 4
    mov [couleur], C_NET
    mov cx, 0
net_loop:
    mov [py], cx
    call draw_rect
    add cx, 12
    cmp cx, 200
    jb net_loop
    pop cx
    ret
draw_net endp

draw_paddle_g proc near
    mov [px], 8
    mov [py], ax
    mov [larg], PAD_W
    mov [haut], PAD_H
    call draw_rect
    ret
draw_paddle_g endp

draw_paddle_d proc near
    mov [px], 314
    mov [py], ax
    mov [larg], PAD_W
    mov [haut], PAD_H
    call draw_rect
    ret
draw_paddle_d endp

draw_ball proc near
    mov [px], ax
    mov [py], bx
    mov [larg], BALL_S
    mov [haut], BALL_S
    call draw_rect
    ret
draw_ball endp

sound_beep proc near
    push ax
    push cx
    in al, 61h
    or al, 2
    out 61h, al
    mov cx, 1800h
sdelay:
    loop sdelay
    in al, 61h
    and al, 0FCh
    out 61h, al
    pop cx
    pop ax
    ret
sound_beep endp

delay proc near
    push ax
    push cx
    push dx
    mov ah, 86h
    mov cx, 0
    mov dx, 4000h
    int 15h
    pop dx
    pop cx
    pop ax
    ret
delay endp

afficher_texte proc near
    push ax
    push dx
    mov ah, 02h
    mov bh, 0
    int 10h
    mov dx, si
    mov ah, 09h
    int 21h
    pop dx
    pop ax
    ret
afficher_texte endp

title_screen proc near
    call clear_screen
    call draw_net

    mov dh, 8
    mov dl, 14
    mov si, offset msg_title
    call afficher_texte

    mov dh, 11
    mov dl, 8
    mov si, offset msg_sub
    call afficher_texte

    mov dh, 14
    mov dl, 10
    mov si, offset msg_start
    call afficher_texte

    mov ah, 00h
    int 16h
    ret
title_screen endp

draw_score_panel proc near
    push ax
    push dx

    mov [px], 0
    mov [py], 0
    mov [larg], 320
    mov [haut], 14
    mov [couleur], C_BG
    call draw_rect

    mov dh, 0
    mov dl, 2
    mov si, offset msg_p1
    call afficher_texte
    mov dl, [score_g]
    add dl, '0'
    mov ah, 02h
    int 21h

    mov dh, 0
    mov dl, 32
    mov si, offset msg_p2
    call afficher_texte
    mov dl, [score_d]
    add dl, '0'
    mov ah, 02h
    int 21h

    pop dx
    pop ax
    ret
draw_score_panel endp

check_input proc near
    push ax
    push bx

check_next:
    mov ah, 01h
    int 16h
    jnz keep_checking  ; If a key IS pressed, skip the jump and process it
    jmp check_done     ; If NO key is pressed (Zero Flag is set), use an unconditional jump to exit

keep_checking:
    mov ah, 00h
    int 16h

    cmp al, 1Bh
    je ci_quit
    cmp al, 'z'
    je p1_up
    cmp al, 's'
    je p1_down
    cmp al, 'Z'
    je p1_up
    cmp al, 'S'
    je p1_down
    cmp al, 'o'
    je p2_up
    cmp al, 'l'
    je p2_down
    cmp al, 'O'
    je p2_up
    cmp al, 'L'
    je p2_down
    cmp ah, 48h
    je p2_up
    cmp ah, 50h
    je p2_down
    jmp check_next

ci_quit:
    mov [quit_flag], 1
    jmp check_next

p1_up:
    mov bx, [pal_g_y]
    sub bx, 8
    cmp bx, 14
    jge p1u_ok
    mov bx, 14
p1u_ok:
    mov [pal_g_y], bx
    jmp check_next

p1_down:
    mov bx, [pal_g_y]
    add bx, 8
    cmp bx, 200 - PAD_H - 2
    jle p1d_ok
    mov bx, 200 - PAD_H - 2
p1d_ok:
    mov [pal_g_y], bx
    jmp check_next

p2_up:
    mov bx, [pal_d_y]
    sub bx, 8
    cmp bx, 14
    jge p2u_ok
    mov bx, 14
p2u_ok:
    mov [pal_d_y], bx
    jmp check_next

p2_down:
    mov bx, [pal_d_y]
    add bx, 8
    cmp bx, 200 - PAD_H - 2
    jle p2d_ok
    mov bx, 200 - PAD_H - 2
p2d_ok:
    mov [pal_d_y], bx
    jmp check_next

check_done:
    pop bx
    pop ax
    ret
check_input endp

reset_balle proc near
    mov word ptr [balle_x], 160
    mov word ptr [balle_y], 100
    mov word ptr [vbx], 2
    mov word ptr [vby], 1
    mov word ptr [speed], 2
    ret
reset_balle endp

update_physics proc near
    push bx
    push cx
    push dx

    mov al, 0

    mov ax, [balle_x]
    mov [old_b_x], ax
    mov ax, [balle_y]
    mov [old_b_y], ax

    mov ax, [balle_x]
    add ax, [vbx]
    mov [balle_x], ax

    mov ax, [balle_y]
    add ax, [vby]
    mov [balle_y], ax

    cmp word ptr [balle_y], 14
    jg test_bas
    mov word ptr [balle_y], 14
    neg word ptr [vby]
    call sound_beep
test_bas:
    cmp word ptr [balle_y], 196
    jl ck_gauche
    mov word ptr [balle_y], 196
    neg word ptr [vby]
    call sound_beep

ck_gauche:
    cmp word ptr [balle_x], 14
    jg ck_droite

    mov ax, [balle_y]
    cmp ax, [pal_g_y]
    jl rate_g
    mov bx, [pal_g_y]
    add bx, PAD_H
    cmp ax, bx
    jg rate_g

    mov ax, [balle_y]
    sub ax, [pal_g_y]
    sub ax, 20
    mov cl, 3
    idiv cl
    cbw
    mov [vby], ax

    mov ax, [speed]
    cmp ax, 7
    jge max_spd
    inc ax
    mov [speed], ax
max_spd:
    mov [vbx], ax
    call sound_beep
    jmp up_done

rate_g:
    inc [score_d]
    call draw_score_panel
    call sound_beep
    cmp [score_d], SCR_MAX
    jne reset_b
    mov [gagnant], 2
    mov al, 1
    jmp up_done
reset_b:
    call reset_balle
    jmp up_done

ck_droite:
    cmp word ptr [balle_x], 306
    jl up_done

    mov ax, [balle_y]
    cmp ax, [pal_d_y]
    jl rate_d
    mov bx, [pal_d_y]
    add bx, PAD_H
    cmp ax, bx
    jg rate_d

    mov ax, [balle_y]
    sub ax, [pal_d_y]
    sub ax, 20
    mov cl, 3
    idiv cl
    cbw
    mov [vby], ax

    mov ax, [speed]
    cmp ax, 7
    jge max_spd2
    inc ax
    mov [speed], ax
max_spd2:
    neg ax
    mov [vbx], ax
    call sound_beep
    jmp up_done

rate_d:
    inc [score_g]
    call draw_score_panel
    call sound_beep
    cmp [score_g], SCR_MAX
    jne reset_b2
    mov [gagnant], 1
    mov al, 1
    jmp up_done
reset_b2:
    call reset_balle

up_done:
    pop dx
    pop cx
    pop bx
    ret
update_physics endp

draw_frame proc near
    push ax
    push bx

    mov [couleur], C_BG
    mov ax, [old_b_x]
    mov bx, [old_b_y]
    call draw_ball

    mov ax, [old_g_y]
    cmp ax, [pal_g_y]
    je skip_eg
    mov [couleur], C_BG
    call draw_paddle_g
skip_eg:
    mov ax, [old_d_y]
    cmp ax, [pal_d_y]
    je skip_ed
    mov [couleur], C_BG
    call draw_paddle_d
skip_ed:

    mov [couleur], C_P1
    mov ax, [pal_g_y]
    mov [old_g_y], ax
    call draw_paddle_g

    mov [couleur], C_P2
    mov ax, [pal_d_y]
    mov [old_d_y], ax
    call draw_paddle_d

    mov [couleur], C_BALL
    mov ax, [balle_x]
    mov bx, [balle_y]
    call draw_ball

    pop bx
    pop ax
    ret
draw_frame endp

game_over_screen proc near
    call clear_screen
    call draw_net

    mov dh, 8
    mov dl, 14
    mov si, offset msg_go
    call afficher_texte

    mov dh, 10
    mov dl, 11
    mov si, offset msg_w1
    call afficher_texte

    mov dl, [gagnant]
    add dl, '0'
    mov ah, 02h
    int 21h

    mov dh, 13
    mov dl, 9
    mov si, offset msg_replay
    call afficher_texte

go_wait:
    mov ah, 00h
    int 16h
    cmp al, 'r'
    je restart_game
    cmp al, 'R'
    je restart_game
    cmp al, 1Bh
    jne go_wait       ; If it's NOT Escape, loop back and wait
    jmp fin           ; If it IS Escape, use a near unconditional jump to reach 'fin'

restart_game:
    mov [score_g], 0
    mov [score_d], 0
    mov [gagnant], 0
    mov [quit_flag], 0
    mov [pal_g_y], 80
    mov [pal_d_y], 80
    call reset_balle
    call clear_screen
    call draw_net
    call draw_score_panel
    ret
game_over_screen endp

debut:
    mov ax, pile
    mov ss, ax
    mov sp, 512
    mov ax, data
    mov ds, ax

    mov ah, 0
    mov al, 13h
    int 10h

    call title_screen
    call clear_screen
    call draw_net
    call draw_score_panel

main_loop:
    call check_input
    cmp [quit_flag], 1
    je fin

    call update_physics
    cmp al, 1
    je go_label

    call draw_frame
    call delay

    jmp main_loop

go_label:
    call game_over_screen
    jmp main_loop

fin:
    mov ah, 0
    mov al, 03h
    int 10h
    mov ah, 4Ch
    int 21h

code ends
end debut
