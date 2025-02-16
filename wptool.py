#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#Author: assismartins.francisco@gmail.com
#Version: 2.1
import subprocess
import re
import sys
import pwd
import urllib.request
import os
import json
import argparse as ap
import logging

class WordPress:
    def __init__(self, usuario, isVPS):
        self.pathwp = []
        self.usuario = Usuario(usuario)
        self.log = Log("/var/cpanel/logs/wptool/usagelog", self.usuario)
        self.isVPS = isVPS
        
    def listarWP(self):
        retorno = ExecTermSafe(['vdetect', '--user={}'.format(self.usuario.getUsuario()), '2>/dev/null'])
        
        if retorno is None:
            print("Sites não foram identificados")
            exit()
        
        rePaths = re.compile(r'::\s+/\S+')
        paths = rePaths.findall(retorno)
        self.pathwp = [path.strip(':: ').strip() for path in paths if path] if retorno else []
        
    def setPath(self, path):
        self.pathwp.append(path)
        
    def getPathWP(self):
        return self.pathwp

    def validaPath(self, pathteste):
        if not os.path.exists(pathteste):
            print(f"Caminho inválido: {pathteste}")
            return False
        userID = os.stat(pathteste).st_uid
        ownerPath = pwd.getpwuid(userID).pw_name
        
        retorno = self.wpExec(pathteste, "core is-installed")
        
        if retorno is not None:
            if os.path.exists(pathteste) and ownerPath == self.usuario.getUsuario():
                return True
        return False

    def wpExec(self, pathwp, wpCommand):
        self.usuario.habilitarShell()
        comando = ['su', '-', self.usuario.getUsuario(), '-c', f"wp --skip-plugins --skip-themes --path={pathwp} {wpCommand} 2>&1"]
        retorno = ExecTermSafe(comando)
        self.usuario.desabilitarShell()
        if retorno is None:
            self.log.registraLog(f"| Ação: {wpCommand} | Caminho : {pathwp} | Resultado : FAILED")
            return None
        else:
            resultado = re.search(r"Success: (.+)|Error: (.+)", retorno) 
            if resultado is not None:
                self.log.registraLog(f"| Ação: {wpCommand} | Caminho: {pathwp} | Resultado: {resultado.group(1)} ")
            else:
                self.log.registraLog(f"| Ação: {wpCommand} | Caminho: {pathwp} | Resultado: output_only ")
        return retorno

class Usuario:
    def __init__(self, usuario):
        self.validarUsuario(usuario)
        self.shellhabilitado = False
        
    def validarUsuario(self, usuario):
        userReserv = ["root", "nobody", "mysql"] 
        if usuario in userReserv:
            print("Usuário reservado inválido")
            exit(1)
            
        userExist = ExecTermSafe(['/usr/sbin/whmapi1', 'validate_system_user', f'user={usuario}'])
            
        if "exists: 1" in userExist:
            self.usuario = usuario  
        else: 
            print("Erro: Usuario inválido")
            exit(2)  
        
    def getUsuario(self):
        return self.usuario    
    
    def habilitarShell(self):
        regex_list = [r'%s' % self.usuario, r'noshell']
        if grepFile("/etc/passwd", regex_list):
            ExecTermSafe(['cppc', '--jailshell', self.usuario])
            self.shellhabilitado = True

    def desabilitarShell(self):
        if self.shellhabilitado:
            ExecTermSafe(['cppc', '--disableshell', self.usuario])

class Log:
    def __init__(self, file_path, usuario):
        self.file_path = file_path
        self.usuario = usuario
        self.logger = logging.getLogger(file_path) 
        self.logger.setLevel(logging.DEBUG)
        
        log_dir = os.path.dirname(file_path)
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        if not os.path.exists(file_path):
            open(file_path, 'w').close()
        
        file_handler = logging.FileHandler(self.file_path)
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] usuario:{} %(message)s'.format(self.usuario.getUsuario()), '%Y-%m-%d %H:%M:%S')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
    def registraLog(self, infoLog):
        self.logger.info(infoLog)

def validarServidor():
    tlds = ("mx", "cl", "co", "br")
    hostname = os.uname()[1]
    if ("hostgator" in hostname or "prodns" in hostname) and os.path.exists('/opt/hgctrl/.zengator'):
        return False
    else:
        try:
            with urllib.request.urlopen("http://api.linkremovido/checkbrand") as retorno:
                brand = retorno.read().decode("utf-8").split("_")[-1].strip()
            if brand in tlds:
                return True
            else:
                print("Execution allowed only on LATAM servers. Exiting")
                exit()
        except urllib.error.URLError:
            print("Erro para identificar brand")
            exit()

def ExecTermSafe(comando):
    try:
        processo = subprocess.run(comando, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        retorno = processo.stdout.decode('utf-8').strip()
        return retorno
    except subprocess.CalledProcessError as e:
        print("Erro ao executar: ", e)
        return None

def grepFile(arquivo, regex_list):
    with open(arquivo, 'r') as arquivo:
        for linha in arquivo:
            if all(re.search(regex, linha) for regex in regex_list):
                return True
    return False

def validarArgumentos():
    argumentos = ap.ArgumentParser(description="Comandos uteis WP Cli")
    
    argumentos.add_argument('-u', '--user', required=True, help="usuario cPanel que será executado")
    argumentos.add_argument('-c', '--command', required=True, help="comando wp-cli que deseja executar")
    
    cmslist = argumentos.add_mutually_exclusive_group(required=True)
    cmslist.add_argument('--path', help="define o diretório da instalação do wordpress")
    cmslist.add_argument('--allpath', action='store_true', help="todas as instalações wordpress do usuario serão consideradas")

    return argumentos.parse_args()

def verificar_acesso():
    usuario_atual = os.geteuid()
    if usuario_atual != 0:  # Verifica se o usuário é root
        print("Este script deve ser executado como root.")
        exit(1)

def main():
    verificar_acesso()
    args = validarArgumentos()
    wp = WordPress(args.user, validarServidor())
        
    if args.path:
        wp.setPath(args.path)
    elif args.allpath:
        wp.listarWP()
    
    # Executar comando fornecido
    for path in wp.getPathWP():
        resultado = wp.wpExec(path, args.command)
        if resultado:
            print(resultado)

if __name__ == "__main__":
    main()
