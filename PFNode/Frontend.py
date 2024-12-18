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

url = "https://cosmological-methodical-gas.xrp-mainnet.quiknode.pro/a16fb7142ff874cfa916f6fea4739a2488b73dec"#"https://s.altnet.rippletest.net:51234/"#
llm_address=''#''#
conn = pyodbc.connect(
    'DRIVER={ODBC Driver 17 for SQL Server};'
    'SERVER=VMI2280960\PF;'
    'DATABASE=PFNode;'
    'UID=PFNode;'
    'PWD=KillThemAll'
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





#TOKEN = ''
TOKEN = ''

# Initialize the client with intents
intents = discord.Intents.default()
intents.message_content = True  # Required for reading message content
intents.dm_messages = True      # Enables handling direct messages
#client = discord.Client(intents=intents)

client = commands.Bot(command_prefix='!', intents=intents)
tree = client.tree  # CommandTree instance

@tasks.loop(seconds=10)
async def get_transactions():
    payload = json.dumps({
      "method": "account_tx",
      "params": [
        {
          "account": "",
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
                    'PWD=KillThemAll'
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
        'PWD=KillThemAll'
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
                    'PWD=KillThemAll'
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
                print(DiscordUser[str(message.author.id)]['PrivateKey'])
                print(DiscordUser[str(message.author.id)]['Address'])
                wallet = Wallet.from_secret(DiscordUser[str(message.author.id)]['PrivateKey'])
                print(wallet.classic_address)
                payment = Payment(
                    account=wallet.classic_address,#DiscordUser[str(message.author.id)]['Address'],
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
                    'PWD=KillThemAll'
                    )
                cursor = conn.cursor()
                cursor.execute("{CALL sp_NewDiscordUserMessage (?, ?, ?)}", (DiscordUser[str(message.author.id)]['DiscordUserKey'],response.result["hash"],message.content[:1000],))
                conn.commit()
                cursor.close()
                conn.close()
            else:
                await message.channel.send('Please register your wallet with /wsb_set_wallet')
        else:
            await message.channel.send('Please register your wallet with /wsb_set_wallet')
    else:
        await client.process_commands(message)    


@tree.command(name="fc_create_wallet", description="Setup your XRP wallet")
async def set_wallet(interaction: discord.Interaction):
    seed = generate_seed()
    wallet = Wallet.from_secret(seed)

    class WalletInfoModal(discord.ui.Modal, title='Setup your XRP wallet'):
        def __init__(self, client):
            super().__init__()
            self.client = client

        address = discord.ui.TextInput(
            label='Address (do not modify)',
            default=wallet.classic_address,
            style=discord.TextStyle.short,
            required=True
        )
        seed = discord.ui.TextInput(
            label='Secret (do not modify)',
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
                'PWD=KillThemAll'
                )
            cursor = conn.cursor()
            cursor.execute("{CALL sp_UpdateDiscordUserAddress (?, ?, ?, ?, ?)}", (DiscordUser[str(interaction.user.id)]['DiscordUserKey'], str(interaction.user.id), DiscordUser[str(interaction.user.id)]['Name'], DiscordUser[str(interaction.user.id)]['Address'], DiscordUser[str(interaction.user.id)]['PrivateKey']))
            conn.commit()
            cursor.close()
            conn.close()
            await interaction.response.send_message(
                "Wallet set successfully. Deposit 15 XRP to your wallet (10 XRP to activate, 5 XRP to use for gas). After, DM bot to start conversation",
                ephemeral=True
            )

    # Create the modal with the client reference and send it
    modal = WalletInfoModal(interaction.client)
    await interaction.response.send_modal(modal)
    
@tree.command(name="fc_store_seed", description="Import your address and secret to the bot")
async def store_seed(interaction: discord.Interaction):
    seed = generate_seed()
    wallet = Wallet.from_secret(seed)

    class StoreSeedModal(discord.ui.Modal, title='Import your XRP wallet'):
        def __init__(self, client):
            super().__init__()
            self.client = client

        address = discord.ui.TextInput(
            label='Address',
            default='',
            style=discord.TextStyle.short,
            required=True
        )
        seed = discord.ui.TextInput(
            label='Secret',
            default='',
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
                'PWD=KillThemAll'
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
    modal = StoreSeedModal(interaction.client)
    await interaction.response.send_modal(modal)
    
@tree.command(name="fc_my_wallet", description="Show your XRP address and secret")
async def show_wallet(interaction: discord.Interaction):
    if str(interaction.user.id) not in DiscordUser:
        await interaction.response.send_message(
                "Unregistered user. Please register with /fc_create_wallet command",
                ephemeral=True
            )
    else:
        
        class PrivateKeyModal(discord.ui.Modal, title='Wallet information'):
            def __init__(self, client):
                super().__init__()
                self.client = client
    
            address = discord.ui.TextInput(
                label='Your address',
                default=DiscordUser[str(interaction.user.id)]['Address'],
                style=discord.TextStyle.short,
                required=True
                )
            seed = discord.ui.TextInput(
                label='Your secret (do not share!)',
                default=DiscordUser[str(interaction.user.id)]['PrivateKey'],
                style=discord.TextStyle.short,
                required=True
                )
            
            async def on_submit(self, interaction: discord.Interaction):
                await interaction.response.send_message(
                    "Wallet was shown",
                    ephemeral=True
                )
        
        # Create the modal with the client reference and send it
        modal = PrivateKeyModal(interaction.client)
        await interaction.response.send_modal(modal)
        
@tree.command(name="fc_reset_context", description="Reset dialogue")
async def show_wallet(interaction: discord.Interaction):
    conn = pyodbc.connect(
                'DRIVER={ODBC Driver 17 for SQL Server};'
                'SERVER=VMI2280960\PF;'
                'DATABASE=PFNode;'
                'UID=PFNode;'
                'PWD=KillThemAll'
                )
    cursor = conn.cursor()
    cursor.execute("UPDATE tbl_DiscordUser SET CurrentDialogueID=NULL WHERE ID= ?", (str(interaction.user.id)))
    conn.commit()
    cursor.close()
    conn.close()    
    await interaction.response.send_message(
                "New dialogue is started. DM bot to start conversation",
                ephemeral=True
            )
    
client.run(TOKEN)
