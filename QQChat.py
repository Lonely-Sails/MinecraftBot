from mcdreforged.api.utils import Serializable
from mcdreforged.api.command import SimpleCommandBuilder, GreedyText
from mcdreforged.api.all import PluginServerInterface, CommandContext, CommandSource

import requests
from os.path import exists
from json import dumps


PLUGIN_METADATA = {
    'id': 'qq_chat',
    'version': '1.0.0',
    'name': 'QQChat',
    'description': '与机器人服务器交互的插件，可以发送消息到 QQ 群。',
    'link': 'https://github.com/Lonely-Sails/Minecraft_QQBot'
}


class Config(Serializable):
    # 机器人服务器的端口
    port: int = 8000
    # 服务器名称
    name: str = 'name'
    # 和机器人服务器的 token 一致
    token: str = 'Your Token'
    # 是否播报服务器开启/关闭
    broadcast_server: bool = True
    # 是否播报玩家进入/离开服务器
    broadcast_player: bool = True
    # 可以不用动，会自动同步
    bot_prefix: str = 'bot_'


class EventSender:
    server: PluginServerInterface = None
    request_url: str = 'http://127.0.0.1:{}'

    def __init__(self, server: PluginServerInterface, port: int):
        self.server = server
        self.request_url = self.request_url.format(port)

    def __request(self, name: str, data: dict):
        data['token'] = config.token
        try: request = requests.post(F'{self.request_url}/{name}', data=dumps(data))
        except Exception: return None
        if request.status_code == 200:
            response = request.json()
            if response.get('Success'):
                return response

    def send_message(self, message: str):
        data = {'token': config.token, 'message': message}
        self.server.logger.info(F'向 QQ 群发送消息 {message}')
        return self.__request('send_message', data)

    def send_startup(self):
        rcon_info = self.read_rcon_info()
        data = {'name': config.name, 'rcon': rcon_info}
        if response := self.__request('server/startup', data):
            self.server.logger.info('发送服务器启动消息成功！')
            config.bot_prefix = response.get('bot_prefix')
            return None
        self.server.logger.error('发送服务器启动消息失败！请检查配置或查看是否启动服务端，然后重试。')

    def send_shutdown(self):
        data = {'name': config.name}
        if self.__request('server/shutdown', data):
            self.server.logger.info('发送服务器关闭消息成功！')
            return None
        self.server.logger.error('发送服务器关闭消息失败！请检查配置或查看是否启动服务端，然后重试。')

    def read_rcon_info(self):
        password, port = None, None
        if not exists('./server/server.properties'):
            self.server.logger.error('服务器配置文件不存在！请联系管理员求助。')
            return None
        with open('./server/server.properties', encoding='Utf-8', mode='r') as file:
            for line in file.readlines():
                if (not line) or line.startswith('#'):
                    continue
                if len(line := line.strip().split('=')) == 2:
                    key, value = line
                    if key == 'enable-rcon' and value == 'false':
                        self.server.logger.error('服务器没有开启 Rcon ！请开启 Rcon 后重试。')
                        return None
                    port = (int(value) if key == 'rcon.port' else port)
                    password = (value if key == 'rcon.password' else password)
        if not (password and port):
            self.server.logger.error('服务器配置文件中没有找到 Rcon 信息！请检查服务器配置文件后重试。')
            return None
        return password, port


config: Config = None
event_sender: EventSender = None


def on_load(server: PluginServerInterface, old):
    def qq(source: CommandSource, content: CommandContext):
        player = 'Console' if source.is_console else source.player
        success = event_sender.send_message(
            F'[{config.name}] <{player}> {content.get("message")}')
        source.reply('§7发送消息成功！§7' if success else '§6发送消息失败！§6')

    global event_sender, config
    config = server.load_config_simple(target_class=Config)
    server.register_help_message('qq', '发送消息到 QQ 群')
    server.logger.info('正在注册指令……')
    command_builder = SimpleCommandBuilder()
    command_builder.command('!!qq <message>', qq)
    command_builder.arg('message', GreedyText)
    command_builder.register(server)
    event_sender = EventSender(server, config.port)


def on_server_stop(server: PluginServerInterface, old):
    server.logger.info('检测到服务器关闭，正在通知机器人服务器……')
    event_sender.send_shutdown()
    if config.broadcast_server:
        event_sender.send_message(F'服务器 [{config.name}] 关闭了！喵~')


def on_server_startup(server: PluginServerInterface):
    server.logger.info('检测到服务器开启，正在连接机器人服务器……')
    event_sender.send_startup()
    if config.broadcast_server:
        event_sender.send_message(F'服务器 [{config.name}] 已经开启辣！喵~')


def on_player_left(server: PluginServerInterface, player: str):
    if config.broadcast_player:
        if config.bot_prefix and player.upper().startswith(config.bot_prefix):
            event_sender.send_message(F'机器人 {player} 离开了 [{config.name}] 服务器。')
            return
        event_sender.send_message(F'玩家 {player} 离开了 [{config.name}] 服务器，呜~')


def on_player_joined(server: PluginServerInterface, player: str, info):
    if config.broadcast_player:
        if config.bot_prefix and player.upper().startswith(config.bot_prefix):
            event_sender.send_message(F'机器人 {player} 加入了 [{config.name}] 服务器！')
            return
        event_sender.send_message(F'玩家 {player} 加入了 [{config.name}] 服务器！喵~')
