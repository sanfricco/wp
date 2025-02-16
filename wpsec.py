#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#Author: assismartins.francisco@gmail.com
#Version: 2.0
import re
import os
from wptool import *  
import tarfile
from datetime import datetime

def backup_path(pathwp):
    backup_dir = f"{pathwp}_backup_{datetime.now().strftime('%Y%m%d%H%M%S')}.tar.gz"
    try:
        with tarfile.open(backup_dir, "w:gz") as tar:
            tar.add(pathwp, arcname=os.path.basename(pathwp))
        print(f"Backup created at {backup_dir}")
        return True
    except Exception as e:
        print(f"Failed to create backup: {e}")
        return False
    
def validarArgumentos():
    argumentos = ap.ArgumentParser()
    
    argumentos.add_argument('-u', '--user', required=True, help="define usuario que será executado")
    
    cmslist = argumentos.add_mutually_exclusive_group(required=True)
    cmslist.add_argument('--path', help="define o diretório da instalação do wordpress")
    cmslist.add_argument('--all', action='store_true', help="todas as instalações wordpress do usuario serão consideradas")
    
    return argumentos.parse_args()

def wpSec(wp):
    wp.usuario.habilitarShell()  

    comando = ['echo', wp.usuario.getUsuario()]
    executante = ExecTermSafe(comando)

    wp.log.registraLog("started_by:{} wp_sites:{}".format(executante, len(wp.pathwp)))

    if os.path.exists('/opt/eig_linux/bin/backuphelper') and not wp.isVPS:
        comando = ['/opt/eig_linux/bin/backuphelper', 'skipuser', wp.usuario.getUsuario()]
        retorno = ExecTermSafe(comando)
        if retorno is None:
            print("Backuphelper failed. Exiting")
            exit(1)

        wp.log.registraLog("Backup:success {}".format(retorno))

    for path in wp.pathwp:
        if wp.validaPath(path):
            if wp.isVPS and not backup_path(path):
                print("Backup failed. Exiting.")
                exit(1)

            comando = ['su', wp.usuario.getUsuario(), '-c', f"wp --skip-plugins --skip-themes --path={path} user list --role=administrator --format=csv --fields=ID,user_login 2>/dev/null| sed 1d"]
            retorno = ExecTermSafe(comando)
            if retorno is None:
                print("Não há administradores em {}".format(path))
                exit()

            usuariosWP = retorno.split('\n')
            usuariosSus = re.compile(r'^(deleted-[0-9a-zA-Z]+|wp_update-[0-9]+|test[0-9]+|wpsupp-user|wpcron[0-9a-zA-Z]+|ismm|itsme|happy|wp-user|wp-blog|xtw[0-9a-zA-Z]+)$')

            blUserPrincipal = True
            idsUsuarios = []
            nomeUsuario = []

            for usuarioWP in usuariosWP:
                if not usuariosSus.match(usuarioWP.split(',')[1]):
                    if blUserPrincipal:
                        userprincipal = usuarioWP.split(',')[0]
                        blUserPrincipal = False
                    idsUsuarios.append(usuarioWP.split(',')[0])
                    nomeUsuario.append(usuarioWP.split(',')[1])
                elif not blUserPrincipal:
                    wp.wpExec(path, "user delete {} --reassign={}".format(usuarioWP.split(',')[0], userprincipal))

            # Reseta as senhas dos usuários
            for idUser in idsUsuarios:
                idUser = str(idUser)
                wp.wpExec(path, "user reset-password {} --show-password".format(idUser))

            # Atualiza plugins, temas e núcleo do WordPress
            wp.wpExec(path, "plugin update --all")
            wp.wpExec(path, "theme update --all")
            wp.wpExec(path, "core update")

            # Configura atualizações automáticas e desativa cron
            wp.wpExec(path, "config set AUTOMATIC_UPDATER_DISABLED false --raw --type=constant")
            wp.wpExec(path, "config set DISABLE_WP_CRON true --raw --type=constant")
        else:
            wp.log.registraLog("checkPath:failed path:{}".format(path))

def main():
    verificar_acesso()
    args = validarArgumentos()
    wp = WordPress(args.user, validarServidor())

    if args.path:
        wp.setPath(args.path)
    elif args.all:
        wp.listarWP()
    for path in wp.pathwp:
        print(path)

    confirmar = input(f"Deseja executar para todos os sites acima? [Y/N] ").strip().upper()
    if confirmar == 'Y':
        wpSec(wp)   
    else:
        print("Encerrando") 
    exit()

    

if __name__ == "__main__":
    main()
