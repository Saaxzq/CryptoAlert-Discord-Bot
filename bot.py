import discord
from discord.ext import tasks
from dotenv import load_dotenv
from discord import app_commands
import requests
import itertools
import traceback
import os

load_dotenv()

#    Pega o token 
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN is None:
    raise ValueError("❌ Token do Discord não encontrado! Verifique o Secrets do Replit.")

#    Últimos preços salvos    
last_prices = {"USD": None, "EUR": None, "BTC": None}
alert_channel_name = "geral"
status_cycle = itertools.cycle(["USD", "EUR", "BTC"])

#    Classe do bot        
class MyBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True 
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def on_ready(self):
        await self.tree.sync()
        print(f"✅ Bot {self.user} conectado e comandos sincronizados globalmente!")
        print("Servidores conectados:")
        for guild in self.guilds:
            print(f" - {guild.name}")
        # Inicia a tarefa de loop para o status
        update_status.start()

bot = MyBot()

#   Função para pegar preços  
def get_prices():
    url = "https://economia.awesomeapi.com.br/last/USD-BRL,EUR-BRL,BTC-BRL"
    try:
        response = requests.get(url)
        data = response.json()
        return {
            "USD": float(data["USDBRL"]["bid"]),
            "EUR": float(data["EURBRL"]["bid"]),
            "BTC": float(data["BTCBRL"]["bid"])
        }
    except Exception as e:
        print(f"❌ Erro ao pegar preços: {e}")
        return last_prices

#      Lista de erros      
@bot.event
async def on_error(event, *args, **kwargs):
    with open("discord_bot_errors.log", "a", encoding="utf-8") as f:
        f.write(f"Erro no evento: {event}\n")
        f.write(traceback.format_exc())
        f.write("\n\n")
    print(f"❌ Erro no evento: {event} (veja discord_bot_errors.log)")

#       Comando /cotacao      
@bot.tree.command(name="cotacao", description="Mostra a cotação do dólar, euro e bitcoin")
async def cotacao(interaction: discord.Interaction):
    global last_prices
    prices = get_prices()

    if last_prices["USD"] is not None:
        diff = prices["USD"] - last_prices["USD"]
        if diff > 0:
            diff_text = f" ({diff:+.2f}) 🔺"
            color = discord.Color.green()
        elif diff < 0:
            diff_text = f" ({diff:+.2f}) 🔻"
            color = discord.Color.red()
        else:
            diff_text = " (0.00)"
            color = discord.Color.greyple()
    else:
        diff_text = ""
        color = discord.Color.greyple()

    embed = discord.Embed(title="💹 Cotações Atuais", color=color)
    embed.add_field(name="💵 Dólar", value=f"R$ {prices['USD']:.2f}{diff_text}", inline=False)
    embed.add_field(name="💶 Euro", value=f"R$ {prices['EUR']:.2f}", inline=False)
    embed.add_field(name="₿ Bitcoin", value=f"R$ {prices['BTC']:.2f}", inline=False)
    embed.set_footer(text="Fonte: AwesomeAPI")

    last_prices = prices
    await interaction.response.send_message(embed=embed)

#  Comando /setcanal  
@bot.tree.command(name="setcanal", description="Define o canal onde os alertas do dólar serão enviados")
@app_commands.describe(nome="Nome do canal")
async def setcanal(interaction: discord.Interaction, nome: str):
    global alert_channel_name
    channel = discord.utils.get(interaction.guild.text_channels, name=nome) # type: ignore
    if channel:
        alert_channel_name = nome
        await interaction.response.send_message(f"✅ Canal de alertas definido para: #{nome}")
    else:
        await interaction.response.send_message(f"❌ Canal '{nome}' não encontrado no servidor.")

#   Loop de status e alertas
@tasks.loop(seconds=10)
async def update_status():
    global last_prices
    prices = get_prices()

    moeda = next(status_cycle)
    valor = prices[moeda]
    activity_text = f"{moeda}: R$ {valor:.2f}"

    try:
        await bot.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(type=discord.ActivityType.watching, name=activity_text)
        )
    except Exception as e:
        print(f"❌ Erro ao alterar o status do bot: {e}")

    channel = discord.utils.get(bot.get_all_channels(), name=alert_channel_name)
    if last_prices["USD"] is not None and channel:
        diff = prices["USD"] - last_prices["USD"] #type: ignore
        if abs(diff) >= 0.20:
            color = discord.Color.green() if diff > 0 else discord.Color.red()
            emoji = "🔺" if diff > 0 else "🔻"
            embed = discord.Embed(
                title=f"{emoji} Dólar mudou!",
                description=f"R$ {last_prices['USD']:.2f} → R$ {prices['USD']:.2f} ({diff:+.2f})",
                color=color
            )
            embed.set_footer(text="Fonte: AwesomeAPI")
            print(f"📢 Alerta enviado: R$ {last_prices['USD']:.2f} → R$ {prices['USD']:.2f}")

            try:
                await channel.send(embed=embed)
            except Exception as e:
                print(f"❌ Erro ao enviar alerta para o canal #{alert_channel_name}: {e}")

    last_prices = prices

@update_status.before_loop
async def before_update_status():
    await bot.wait_until_ready()

if __name__ == '__main__':
    bot.run(TOKEN)