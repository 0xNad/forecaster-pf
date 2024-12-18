import requests
import pandas as pd
import pymssql
import csv
import subprocess
import xrpl
import json
from xrpl.wallet import Wallet
from xrpl.clients import JsonRpcClient
import xrpl.transaction
from xrpl.models.transactions import Payment, Memo
from xrpl.utils import str_to_hex
import math
import pyodbc
from collections import defaultdict
import time
from datetime import datetime, timedelta
import openai
from openai import OpenAI
from message_handler.message_handler import compose

def Answering():
    print('Working')
    url = "https://cosmological-methodical-gas.xrp-mainnet.quiknode.pro/a16fb7142ff874cfa916f6fea4739a2488b73dec"#"https://s.altnet.rippletest.net:51234/"
    llm_address='rnSdLVPDy6s8N2dWHDS7LQ87zchNn6W6ix'#'rN8Uh543MpEyv6Pyc1JNexYRWzKUk3vCZV'
#    openai.api_key=""
    LLMClient=OpenAI(api_key="")
    print('Working1') 
    payload = json.dumps({
      "method": "account_tx",
      "params": [
        {
          "account": "rN8Uh543MpEyv6Pyc1JNexYRWzKUk3vCZV",
          "binary": False,
          "forward": False,
          "ledger_index_max": -1,
          "ledger_index_min": -1,
          "limit": 1000
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
        if ("Memos" in tran["tx"]) and (tran["tx"]["Destination"]==llm_address):
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
    
    cursor = conn.cursor()
    query = """SELECT MessageKey, Role, Text, MainMessageKey
                FROM tbl_Message m
                INNER JOIN 
                (SELECT MessageKey AS MainMessageKey, DialogueID
                FROM [dbo].[tbl_Message] 
                WHERE Status='Created' AND Type='DiscordDM' AND [TransactionKey] IS NOT NULL) mm 
                ON mm.DialogueID=m.DialogueID
                ORDER BY m.Timestamp"""
    
    cursor.execute(query)
    
    Messages = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    
    
    
    
    
    conn = pyodbc.connect(
            'DRIVER={ODBC Driver 17 for SQL Server};'
            'SERVER=VMI2280960\PF;'
            'DATABASE=PFNode;'
            'UID=PFNode;'
            'PWD=KillThemAll'
            )
    
    query = """SELECT DISTINCT m.MessageKey, a.Address, m.Text
                FROM [dbo].[tbl_Message] m
                INNER JOIN tbl_DiscordUser du ON du.DiscordUserKey=m.DiscordUserKey
                INNER JOIN tbl_Address a ON a.DiscordUserKey=du.DiscordUserKey
                WHERE Status='Created' AND Type='DiscordDM' AND [TransactionKey] IS NOT NULL"""
    Addresses = pd.read_sql(query, conn)
    
    conn.close()
    
    Addresses.set_index('MessageKey', inplace=True)
    Addresses = Addresses.to_dict('index')
    
    
    
    AggregatedMessages = defaultdict(list)
    for Message in Messages:
        AggregatedMessages[Message.MainMessageKey].append({"role": Message.Role, "content": Message.Text})
    
        
    AggregatedMessages = dict(AggregatedMessages)
        
    print(AggregatedMessages)
    print("-------------")
    LLMURL = "https://api.corcel.io/v1/text/cortext/chat"
    
    client = JsonRpcClient(url)
    sender_address = llm_address
    sender_secret = ""#""#
    wallet = Wallet.from_secret(sender_secret)
    


    
    for MessageKey in AggregatedMessages.keys():
        print("---")
        LastMessage=Addresses[MessageKey]["Text"]
        
        Response = LLMClient.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": "The next user message may content a question about specific Polymarket market or it may not contain question. You must answer exactly 'YES' if it is contain and exactly 'NO' if not. Please answer only with this 2 words (YES or NO) because your answer will be processed programatically"},
                      {"role": "user","content": LastMessage}])
        if "YES" in str(Response.choices[0].message.content).upper():
            ExtendedAnswer=compose(LastMessage)
            AggregatedMessages[MessageKey].append({"role": "assistant", "content": ExtendedAnswer})
            AggregatedMessages[MessageKey].append({"role": "user", "content": "Your last (previous) answer (message) in our dialogue was from a specialized agent but without knowledge about our previous messages. Please modify the last answer with all of our dialog in mind"})
            Response = LLMClient.chat.completions.create(model="gpt-4o",messages=AggregatedMessages[MessageKey])
        else:
            Response = LLMClient.chat.completions.create(model="gpt-4o",messages=AggregatedMessages[MessageKey])
            
  
        AgentResponceMessage=str(Response.choices[0].message.content)
        for StartIndex in range(0, len(AgentResponceMessage), 1000):
            StringPart = AgentResponceMessage[StartIndex:StartIndex+1000] 
            payment = Payment(
                account=wallet.address,
                amount="1",
                destination=Addresses[MessageKey]["Address"],
                memos=[Memo(memo_data=str_to_hex(StringPart))]
            )
            
            RPLResponse = xrpl.transaction.submit_and_wait(payment, client, wallet)
            conn = pyodbc.connect(
                'DRIVER={ODBC Driver 17 for SQL Server};'
                'SERVER=VMI2280960\PF;'
                'DATABASE=PFNode;'
                'UID=PFNode;'
                'PWD=KillThemAll'
                )
            cursor = conn.cursor()
    
            cursor.execute("{CALL sp_NewPFNodeMessage (?, ?, ?)}", (Addresses[MessageKey]["Address"],RPLResponse.result["hash"],StringPart))
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
        cursor = conn.cursor()
        cursor.execute("UPDATE tbl_Message SET Status='Processed' WHERE MessageKey= ?", (MessageKey))
        conn.commit()
        cursor.close()
        conn.close()
    
    
    
    
    
    
while True:
    Answering()
    time.sleep(1)