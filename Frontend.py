import discord
import requests
from xrpl.wallet import Wallet
from xrpl.core.keypairs import generate_seed
from xrpl.clients import JsonRpcClient
import xrpl.transaction
from xrpl.models.transactions import Payment, Memo
from xrpl.utils import str_to_hex
from discord.ext import commands, tasks
import pyodbc
import pandas as pd
from xrpl.asyncio.transaction import submit_and_wait
from xrpl.asyncio.clients import AsyncJsonRpcClient
import json
import time
from datetime import datetime, timedelta

url = "https://s.altnet.rippletest.net:51234/"#"https://restless-autumn-hill.xrp-mainnet.quiknode.pro/7b09a739f7e91724f3edb58867e7b28ebb1b9c0e"
llm_address='rN8Uh543MpEyv6Pyc1JNexYRWzKUk3vCZV'
conn = pyodbc.connect(
    'DRIVER={ODBC Driver 17 for SQL Server};'
    'SERVER=VMI2280960\PF;'
    'DATABASE=PFNode;'
    'UID=PFNode;'
    'PWD='
)

# Read data into a DataFrame
query = """SELECT 
       du.[DiscordUserKey]
      ,du.[ID]
      ,du.[Name]
      ,du.[CurrentDialogueID]
	  ,ISNULL(a.[Address],'') AS Address
      ,a.[Seed]
      ,a.[PublicKey]
      ,a.[PrivateKey]
  FROM [PFNode].[dbo].[tbl_DiscordUser] du
  LEFT JOIN [PFNode].[dbo].[tbl_Address] a ON a.DiscordUserKey=du.DiscordUserKey"""
DiscordUserDataFrame = pd.read_sql(query, conn)

conn.close()

DiscordUserDataFrame.set_index('ID', inplace=True)

# Convert DataFrame to a dictionary
DiscordUser = DiscordUserDataFrame.to_dict('index')





# Load the bot token from an environment variable for security
#TOKEN = ''
TOKEN = ''


# Initialize the client with intents
intents = discord.Intents.default()
intents.message_content = True  # Required for reading message content
intents.dm_messages = True      # Enables handling direct messages
#client = discord.Client(intents=intents)

client = commands.Bot(command_prefix='!', intents=intents)
tree = client.tree  # CommandTree instance

@tasks.loop(seconds=30)
async def get_transactions():
    payload = json.dumps({
      "method": "account_tx",
      "params": [
        {
          "account": "rN8Uh543MpEyv6Pyc1JNexYRWzKUk3vCZV",
          "binary": False,
          "forward": False,
          "ledger_index_max": -1,
          "ledger_index_min": -1,
          "limit": 100
        }
      ],
      "id": 1,
      "jsonrpc": "2.0"
    })
    headers = {
      'Content-Type': 'application/json'
    }

    response = requests.request("POST", url, headers=headers, data=payload)
    response = response.json()

    for tran in response["result"]["transactions"]:
        if ("Memos" in tran["tx"]) and (tran["tx"]["Account"]==llm_address):
            conn = pyodbc.connect(
                    'DRIVER={ODBC Driver 17 for SQL Server};'
                    'SERVER=VMI2280960\PF;'
                    'DATABASE=PFNode;'
                    'UID=PFNode;'
                    'PWD='
                    )
            cursor = conn.cursor()
            cursor.execute("{CALL sp_NewTransaction (?, ?, ?, ?, ?, ?)}", (datetime(2000, 1, 1) + timedelta(seconds=tran["tx"]["date"]),tran["tx"]["hash"],tran["tx"]["Account"],tran["tx"]["Destination"],tran["tx"]["Amount"],bytes.fromhex(tran["tx"]["Memos"][0]["Memo"]["MemoData"]).decode("utf-8")))
            conn.commit()
            cursor.close()
            conn.close()
            
            
    conn = pyodbc.connect(
        'DRIVER={ODBC Driver 17 for SQL Server};'
        'SERVER=VMI2280960\PF;'
        'DATABASE=PFNode;'
        'UID=PFNode;'
        'PWD='
        )


    query = """SELECT
            du.ID,
            [MessageKey],
            [Text]
            FROM [dbo].[tbl_Message] m
            INNER JOIN tbl_DiscordUser du ON du.DiscordUserKey=m.DiscordUserKey
            WHERE Status='Created' AND Type='LLMAnswer' AND [TransactionKey] IS NOT NULL
            ORDER BY Timestamp"""
    LLMMessage = pd.read_sql(query, conn)
    #LLMMessage.set_index('DiscordUserKey', inplace=True)
    #LLMMessage = LLMMessage.to_dict('index')
    conn.close() 
    for index, row in LLMMessage.iterrows():
        print(LLMMessage.at[index,'ID'])
        user = await client.fetch_user(int(LLMMessage.at[index,'ID']))
        await user.send(LLMMessage.at[index,'Text'])
        conn = pyodbc.connect(
                    'DRIVER={ODBC Driver 17 for SQL Server};'
                    'SERVER=VMI2280960\PF;'
                    'DATABASE=PFNode;'
                    'UID=PFNode;'
                    'PWD='
                    )
        cursor = conn.cursor()
        cursor.execute("UPDATE tbl_Message SET Status='Processed' WHERE MessageKey= ?", (int(LLMMessage.at[index,'MessageKey'])))
        conn.commit()
        cursor.close()
        conn.close()

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    try:
        synced = await tree.sync()
        print(f'Synced {len(synced)} command(s)')
        get_transactions.start()
    except Exception as e:
        print(e) 
        
@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if isinstance(message.channel, discord.DMChannel):
        if str(message.author.id) in DiscordUser:
            if DiscordUser[str(message.author.id)]['Address']!='':
                RippleClient = AsyncJsonRpcClient(url)#JsonRpcClient(url)
                wallet = Wallet.from_secret(DiscordUser[str(message.author.id)]['PrivateKey'])
                payment = Payment(
                    account=DiscordUser[str(message.author.id)]['Address'],
                    amount="1",
                    destination=llm_address,
                    memos=[Memo(memo_data=str_to_hex(message.content[:1000]))]
                )
    
                
                response = await xrpl.asyncio.transaction.submit_and_wait(payment, RippleClient, wallet)
                #response = response.json()
                conn = pyodbc.connect(
                    'DRIVER={ODBC Driver 17 for SQL Server};'
                    'SERVER=VMI2280960\PF;'
                    'DATABASE=PFNode;'
                    'UID=PFNode;'
                    'PWD='
                    )
                cursor = conn.cursor()
                cursor.execute("{CALL sp_NewDiscordUserMessage (?, ?, ?)}", (DiscordUser[str(message.author.id)]['DiscordUserKey'],response.result["hash"],message.content[:1000],))
                conn.commit()
                cursor.close()
                conn.close()
                await message.channel.send("Message is processing")
            else:
                await message.channel.send('Please register your wallet with /wsb_set_wallet')
        else:
            await message.channel.send('Please register your wallet with /wsb_set_wallet')
    else:
        await client.process_commands(message)    


@tree.command(name="wsb_set_wallet", description="Setup your XRP wallet for WSB Mode bot")
async def set_wallet(interaction: discord.Interaction):
    seed = generate_seed()
    wallet = Wallet.from_secret(seed)
    print("Classic Address:", wallet.classic_address)
    print("Seed:", wallet.seed)
    print("Public Key:", wallet.public_key)
    print("Private Key:", wallet.private_key)

    class WalletInfoModal(discord.ui.Modal, title='Setup your XRP wallet'):
        def __init__(self, client):
            super().__init__()
            self.client = client

        address = discord.ui.TextInput(
            label='Insert your own address or use this',
            default=wallet.classic_address,
            style=discord.TextStyle.short,
            required=True
        )
        seed = discord.ui.TextInput(
            label='Insert our own address secret or keep this',
            default=wallet.seed,
            style=discord.TextStyle.short,
            required=True
        )

        async def on_submit(self, interaction: discord.Interaction):
            if str(interaction.user.id) not in DiscordUser:
        
                DiscordUser[str(interaction.user.id)] = {
                    'DiscordUserKey': None,
                    'ID': '',
                    'CurrentDialogueID' : '',
                    'Address': '',
                    'Name': '',
                    'PrivateKey': '',
                    
                }
            DiscordUser[str(interaction.user.id)]['Address']=str(self.address)
            DiscordUser[str(interaction.user.id)]['Name']=str(interaction.user.name)
            DiscordUser[str(interaction.user.id)]['PrivateKey']=str(self.seed)
            conn = pyodbc.connect(
                'DRIVER={ODBC Driver 17 for SQL Server};'
                'SERVER=VMI2280960\PF;'
                'DATABASE=PFNode;'
                'UID=PFNode;'
                'PWD='
                )
            cursor = conn.cursor()
            cursor.execute("{CALL sp_UpdateDiscordUserAddress (?, ?, ?, ?, ?)}", (DiscordUser[str(interaction.user.id)]['DiscordUserKey'], str(interaction.user.id), DiscordUser[str(interaction.user.id)]['Name'], DiscordUser[str(interaction.user.id)]['Address'], DiscordUser[str(interaction.user.id)]['PrivateKey']))
            conn.commit()
            cursor.close()
            conn.close()
            await interaction.response.send_message(
                "Wallet set successfully",
                ephemeral=True
            )

    # Create the modal with the client reference and send it
    modal = WalletInfoModal(interaction.client)
    await interaction.response.send_modal(modal)
    
@tree.command(name="wsb_show_secret", description="Show your XRP wallet private key")
async def show_wallet(interaction: discord.Interaction):
    if str(interaction.user.id) not in DiscordUser:
        await interaction.response.send_message(
                "Unregistered user. Please register with /set_wallet command",
                ephemeral=True
            )
    else:
        
        class PrivateKeyModal(discord.ui.Modal, title='Your private key'):
            def __init__(self, client):
                super().__init__()
                self.client = client
    
            address = discord.ui.TextInput(
                label='',
                default=DiscordUser[str(interaction.user.id)]['Address'],
                style=discord.TextStyle.short,
                required=True
                )
            seed = discord.ui.TextInput(
                label='',
                default=DiscordUser[str(interaction.user.id)]['PrivateKey'],
                style=discord.TextStyle.short,
                required=True
                )
            
            async def on_submit(self, interaction: discord.Interaction):
                await interaction.response.send_message(
                    "Private key was shown",
                    ephemeral=True
                )
        
        # Create the modal with the client reference and send it
        modal = PrivateKeyModal(interaction.client)
        await interaction.response.send_modal(modal)
    
    
    
client.run(TOKEN)
