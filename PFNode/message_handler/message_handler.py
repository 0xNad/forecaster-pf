
import os
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from message_handler.polymarket.polymarket import Polymarket
from message_handler.polymarket.gamma import GammaMarketClient
from message_handler.utils.objects import PolymarketEvent
import json
from ast import literal_eval
from typing import List

os.environ["OPENAI_API_KEY"] = ""
SYSTEM_PROMPT = """You are a specialized assistant designed to be an AI-driven Polymarket guide.
    Your primary goals are to:
- Analyze user preferences, market trends, and historical data to suggest personalized trading opportunities.
- Use relevant data (e.g., social sentiment, trading volume, news) to assess market sentiment.
- Summarize sentiment trends and explain their potential impact on market outcomes.
- Provide clear, data-driven insights and strategies to help users make informed trading decisions.
- Avoid generic or vague advice—focus on concrete, actionable recommendations.

Given the information about market, answer the user's question.

Market information:
{market_info}
"""
model = ChatOpenAI(model="gpt-4o-mini")


def response(user_input: str, market_info: dict) -> str:
    messages = [
        SystemMessage(SYSTEM_PROMPT.format(market_info=json.dumps(market_info, indent=2))),
        HumanMessage(user_input)
    ]
    answer = model.invoke(messages)
    return answer.content


def conclusion(user_input: str, analytics: List[dict]):
    # info = '\n'.join(analytics)
    info = json.dumps(analytics, indent=2)
    system_prompt = f"""You are a specialized assistant designed to be an AI-driven Polymarket guide.
    Your primary goals are to:
- Analyze user preferences, market trends, and historical data to suggest personalized trading opportunities.
- Use relevant data (e.g., social sentiment, trading volume, news) to assess market sentiment.
- Summarize sentiment trends and explain their potential impact on market outcomes.
- Provide clear, data-driven insights and strategies to help users make informed trading decisions.
- Avoid generic or vague advice—focus on concrete, actionable recommendations.

    Given the summary information about each market inside event and about event, answer the user's question.

    Markets information:
    {info}
"""
    print(system_prompt)
    messages = [
        SystemMessage(system_prompt),
        HumanMessage(user_input)
    ]
    answer = model.invoke(messages)
    return answer.content


def get_relevant_event(user_input: str) -> int:
    gm = GammaMarketClient()
    # markets = gm.get_current_markets(500)
    events = get_all_current_events()
    events_clean = []
    for event in events:
        # markets_clean.append(f"""id: {market.get("id")} name: {market.get("question")};""")
        events_clean.append({'id':event.get("id"),'name':event.get("title")})

    messages = [
        SystemMessage(f"""
Given the user input, return ONLY ID of the most relevant market from the list below.
If there is no market related to question, return id equals to 0.
Give your response in JSON format, e.g. {{'id': '123456'}}, {{'id': '0'}}
List of markets: {json.dumps(events_clean, indent=2)}
"""),
        HumanMessage(user_input)
    ]
    answer = model.invoke(messages)
    id = literal_eval(answer.content).get("id")
    print("relevant id found: ", id)
    return id



def get_all_current_events() -> List[PolymarketEvent]:
    gm = GammaMarketClient()
    cont = True
    limit = 100
    offset = 0
    events = []
    while cont:
        params = {
            "active": True,
            "closed": False,
            "archived": False,
            "limit": limit,
            "offset": offset
        }
        batch = gm.get_events(params)
        events.extend(batch)
        if len(batch) < limit:
            cont = False
        offset = offset + limit
    print("total events found: ", len(events))
    return events


def get_market_info(market_id: int) -> dict:
    gm = GammaMarketClient()
    market = gm.get_market(market_id)
    market_info = {
        'id': market.get('id'),
        'question': market.get('question'),
        'startDate': market.get("startDate"),
        'endDate': market.get('endDate'),
        'description': market.get('description'),
        'outcomes': market.get('outcomes'),
        'outcomePrices': market.get('outcomePrices'),
        'volume': market.get('volume'),
        'orderPriceMinTickSize': market.get('orderPriceMinTickSize'),
        'orderMinSize': market.get('orderMinSize'),
        'volumeNum': market.get('volumeNum'),
        'liquidityNum': market.get('liquidityNum'),
        'commentsEnabled': market.get('commentsEnabled'),
        'volume24hr': market.get('volume24hr'),
        'clobTokenIds': market.get('clobTokenIds'),
        'volume24hrClob': market.get('volume24hrClob'),
        'volumeClob': market.get('volumeClob'),
        'liquidityClob': market.get('liquidityClob'),
        'umaBond': market.get('umaBond'),
        'umaReward': market.get('umaReward'),
        'rewardsMinSize': market.get('rewardsMinSize'),
        'rewardsMaxSpread': market.get('rewardsMaxSpread'),
        'spread': market.get('spread'),
        'oneDayPriceChange': market.get('oneDayPriceChange'),
        'lastTradePrice': market.get('lastTradePrice'),
        'bestBid': market.get('bestBid'),
        'bestAsk': market.get('bestAsk'),
    }
    return market_info


def compose(user_input: str) -> str:
    event_id = int(get_relevant_event(user_input))
    if event_id == 0:
        return "Sorry, can't find relevant markets."
    gm = GammaMarketClient()
    events = gm.get_events(querystring_params={"id": event_id})
    event = events[0]
    event_info = {
        'id': event.get('id'),
        'title': event.get('title'),
        'startDate': event.get("startDate"),
        'endDate': event.get('endDate'),
        'description': event.get('description'),
        'volume': event.get('volume'),
        'volume24hr': event.get('volume24hr'),
        'liquidity': event.get('liquidity'),
        'liquidityClob': event.get('liquidityClob'),
    }
    markets_analycits = []

    event_analysis = response(user_input, event_info)
    markets_analycits.append({"id": 0, "title": "EVENT OVERALL", "summary": event_analysis})

    markets = event.get("markets")
    for market in markets:
        market_info = get_market_info(market.get("id"))
        market_analysis = response(user_input, market_info)
        markets_analycits.append({"id": market_info.get("id"), "title": market_info.get("question"), "summary": market_analysis})

    answer = conclusion(user_input, markets_analycits)
    return answer








