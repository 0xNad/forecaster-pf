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

def Answering():
    print('Working')
    url = "https://s.altnet.rippletest.net:51234/"#"https://restless-autumn-hill.xrp-mainnet.quiknode.pro/7b09a739f7e91724f3edb58867e7b28ebb1b9c0e"
    llm_address='rN8Uh543MpEyv6Pyc1JNexYRWzKUk3vCZV'
    LLMClient=OpenAI(api_key="sk-proj-")
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
            'PWD='
            )
    
    query = """SELECT DISTINCT m.MessageKey, a.Address
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
    sender_secret = "sEd7jZE8G1MpmtFh7VbqXU6N5Zki1Cs"
    wallet = Wallet.from_secret(sender_secret)
    


    
    for MessageKey in AggregatedMessages.keys():
        
        Response = LLMClient.chat.completions.create(
            model="gpt-4o",
            messages=AggregatedMessages[MessageKey]
            )
        Response = Response.json()

        
        payment = Payment(
            account=wallet.address,
            amount="1",
            destination=Addresses[MessageKey]["Address"],
            memos=[Memo(memo_data=str_to_hex(str(Response["choices"][0]["message"])[:1000]))]
        )
        
        RPLResponse = xrpl.transaction.submit_and_wait(payment, client, wallet)
        #RPLResponse = RPLResponse.json()
        conn = pyodbc.connect(
            'DRIVER={ODBC Driver 17 for SQL Server};'
            'SERVER=VMI2280960\PF;'
            'DATABASE=PFNode;'
            'UID=PFNode;'
            'PWD='
            )
        cursor = conn.cursor()
        print(Response[0]["choices"][0]["message"]["content"][:1000])
        cursor.execute("{CALL sp_NewPFNodeMessage (?, ?, ?)}", (Addresses[MessageKey]["Address"],RPLResponse.result["hash"],str(Response[0]["choices"][0]["message"]["content"])[:1000]))
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
        cursor = conn.cursor()
        cursor.execute("UPDATE tbl_Message SET Status='Processed' WHERE MessageKey= ?", (MessageKey))
        conn.commit()
        cursor.close()
        conn.close()
    
    
    
    
    
    
while True:
    Answering()
    time.sleep(1)
