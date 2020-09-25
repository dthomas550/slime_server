import os, shutil, datetime, fileinput, requests, time, sys, mctools
from file_read_backwards import FileReadBackwards
from bs4 import BeautifulSoup

server_functions_path = os.getcwd()
folder_timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H-%M')
new_server_url = 'https://www.minecraft.net/en-us/download/server'

# Updates variables as needed.
discord_bot_token_file = '/home/slime/mc_bot_token.txt'
# This is where Minecraft server, world backups and some discord bot files will be saved, so make sure this is an absolute path and is where you want it.
# The setup_directories() function uses os.makedirs(), which will recursively make subdirectories if they don't exists already. Read more: https://www.tutorialspoint.com/python/os_makedirs.htm
minecraft_folder_path = '/mnt/c/Users/DT/Desktop/MC'

server_path = f"{minecraft_folder_path}/server"
world_backups_path = f"{minecraft_folder_path}/world_backups"
server_backups_path = f"{minecraft_folder_path}/server_backups"
server_jar_file = f'{server_path}/server.jar'
server_log_file = f"{server_path}/output.txt"
server_properties_file = f"{server_path}/server.properties"
discord_bot_file = f"{server_functions_path}/discord_mc_bot.py"
discord_bot_log_file = f"{server_functions_path}/bot_log.txt"
discord_bot_properties_file = f"{server_path}/discord-bot.properties"
command_info_file = "command_info.csv"

# Can adjust java arguments as needed for your system.
java_args = f'java -Xmx2G -Xms1G -jar {server_jar_file} nogui java 2>&1 | tee -a output.txt'
start_server_command = f'tmux send-keys -t mcserver:1.0 "{java_args}" ENTER'

def lprint(arg1=None, arg2=None):
    if type(arg1) is str:
        msg = arg1
        user = 'Script'
    else:
        try: user = arg1.message.author
        except: user = 'N/A'
        msg = arg2

    output = f"{datetime.datetime.now()} | ({user}) {msg}"

    with open(discord_bot_log_file, 'a') as file:
        file.write(output + '\n')

    print(output)

def setup_directories():
    try:
        os.makedirs(server_path)
        os.makedirs(world_backups_path)
        os.makedirs(server_backups_path)
    except: print("Error: Something went wrong setup up necessary directory structure.")

def start_tmux_session():
    try:
        os.system('tmux new -d -s mcserver')
        os.system('tmux send-keys -t mcserver:1.0 "tmux split-window -v" ENTER')
        time.sleep(1)
        os.system(f'tmux send-keys -t mcserver:1.1 "python3 {discord_bot_file}" ENTER')
    except: lprint("Error starting required detached tmux session with 2 windows with name: mcserver")

def start_minecraft_server():
    # Fix: 'java.lang.Error: Properties init: Could not determine current working' error
    os.system('tmux send-keys -t mcserver:1.0 "cd /" ENTER')
    os.system(f'tmux send-keys -t mcserver:1.0 "cd {server_path}" ENTER')

    os.chdir(server_path)
    # Tries starting new detached tmux session.
    if not os.system(start_server_command): 
        return True

def get_output(file, lines=10, match='placeholder match'):
    log_data = match_found = ''
    with FileReadBackwards(file) as file:
        for i in range(lines):
            line = file.readline()
            if match in line:
                match_found = line
                break
            log_data += line

    if match_found:
        return match_found
    return log_data

def get_from_index(path, index): 
    return os.listdir(path)[index]

def fetch_backups(path, amount=5):
    backups = []
    for item in os.listdir(path)[:amount]:
        if os.path.isdir(path + '/' + item):
            backups.append(item)
    return backups


def create_backup(name, src, dst):
    if not os.path.isdir(dst):
        os.makedirs(dst)

    new_name = f"({folder_timestamp}) {get_minecraft_version()} {name}"
    new_backup_path = dst + '/' + new_name
    shutil.copytree(src, new_backup_path)

    if os.path.isdir(new_backup_path):
        lprint("Backed up to: " + new_backup_path)
        return new_name
    else:
        lprint("Error creating backup at: " + new_backup_path)
        return False

def restore_backup(backup, dst, reset=False):
    try: shutil.rmtree(dst)
    except: 
        lprint("Error deleting: " + dst)
        return False

    # This function is used in ?rebirth discord command to create a new world.
    if reset: return True

    try: 
        shutil.copytree(backup, server_path + dst)
    except: lprint("Error restoring: " + str(backup))
    
def delete_backup(backup):
    try:
        shutil.rmtree(backup)
        return True
    except: lprint("Error deleting: " + str(backup))

# Downloads latest server.jar from Minecraft website in current server folder.
def download_new_server():
    os.chdir(minecraft_folder_path)
    jar_download_url = ''

    minecraft_website = requests.get(new_server_url)
    soup = BeautifulSoup(minecraft_website.text, 'html.parser')
    # Finds Minecraft server.jar urls in div class.
    div_agenda = soup.find_all('div', class_='minecraft-version')
    for i in div_agenda[0].find_all('a'):
        jar_download_url = f"{i.get('href')}"

    if not jar_download_url: return

    mc_ver = get_minecraft_version(get_latest=True)
    # Saves new server.jar in current server.
    with open(server_path + '/server.jar', 'wb') as jar_file:
        jar_file.write(requests.get(jar_download_url).content)

    # Updates server discord-bot.properties file. server.properties will remove foreign data on server start.
    if not os.path.isfile(discord_bot_properties_file):
        with open(discord_bot_properties_file, 'w+') as file:
            file.write('version=' + mc_ver)
    else:
        with fileinput.FileInput(discord_bot_properties_file, inplace=True) as file:
            for line in file:
                if file.isfirstline():
                    print('version=' + mc_ver, end='\n')
                else: print(line, end='')

    with open(server_path + '/eula.txt', 'w') as file:
        file.write('eula=true')

    return mc_ver

# Gets server version from file or from website.
def get_minecraft_version(get_latest=False):
    # Returns server version from discord-server.properties file located in same folder as server.jar.
    if not get_latest:
        return edit_properties('version', file_path=discord_bot_properties_file)[0].split('=')[1]

    soup = BeautifulSoup(requests.get(new_server_url).text, 'html.parser')
    for i in soup.findAll('a'):
        # Returns Minecraft server version by splitting up string and extracting only numbers then recombining.
        if i.string and 'minecraft_server' in i.string:
            return '.'.join(i.string.split('.')[1:][:-1])

# Reads server.properties file and edits inplace.
def edit_properties(target_property=None, value='', file_path=server_properties_file):
    os.chdir(server_path)
    # Return data for other script uses, and one specifically for Discord.
    return_line = discord_return = ''
    with fileinput.FileInput(file_path, inplace=True, backup='.bak') as file:
        for line in file:
            split_line = line.split('=', 1)
            if target_property == 'all':
                discord_return += F"`{line.rstrip()}`\n"
                return_line += line.strip()
                print(line, end='')
            elif target_property in split_line[0] and len(split_line) > 1:
                if value:
                    split_line[1] = value
                    new_line = '='.join(split_line)
                    discord_return = f"Updated Property:`{line} > `{new_line}`.\nRestart to apply changes."
                    return_line = line
                    print(new_line, end='\n')
                else:
                    discord_return = f"`{'='.join(split_line)}`"
                    return_line = '='.join(split_line)
                    print(line, end='')
            else: print(line, end='')

    # Sends Discord message saying property not found.
    if return_line:
        return return_line, discord_return
    else: return return_line, "404: Property not found!"

# Functions for discord bot.
def get_server_from_index(index): return get_from_index(server_backups_path, index)
def get_world_from_index(index): return get_from_index(world_backups_path, index)

def fetch_servers(amount=5): return fetch_backups(server_backups_path, amount)
def fetch_worlds(amount=5): return fetch_backups(world_backups_path, amount)

def backup_server(name='server_backup'): return create_backup(name, server_path, server_backups_path)
def backup_world(name="world_backup"): return create_backup(name, server_path + '/world', world_backups_path)

def restore_server(server=None, reset=False): return restore_backup(server, server_path, reset)
def restore_world(world=None, reset=False): return restore_backup(world, server_path + '/world', reset)

def delete_server(server): return delete_backup(server_backups_path + '/' + server)
def delete_world(world): return delete_backup(world_backups_path + '/' + world)

if __name__ == '__main__':
    if 'setup' in sys.argv:
        setup_directories()
        start_tmux_session()
        start_minecraft_server()
