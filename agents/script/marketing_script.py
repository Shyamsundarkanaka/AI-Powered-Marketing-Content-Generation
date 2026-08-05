"""Generate concise Instagram Reel scripts from campaign briefs."""
from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Mapping
from agents.gemini import StructuredGenerator
from agents.product_understanding.campaign_brief import CampaignBrief
@dataclass(frozen=True)
class MarketingScript:
    hook:str; voiceover:str; on_screen_text:tuple[str,...]; call_to_action:str; estimated_duration_seconds:int
SCHEMA={"type":"object","required":["hook","voiceover","on_screen_text","call_to_action","estimated_duration_seconds"],"properties":{"hook":{"type":"string"},"voiceover":{"type":"string"},"on_screen_text":{"type":"array","items":{"type":"string"}},"call_to_action":{"type":"string"},"estimated_duration_seconds":{"type":"integer","minimum":15,"maximum":45}}}
def _s(data:Mapping[str,object],key:str)->str:
    value=data.get(key)
    if not isinstance(value,str) or not value.strip(): raise ValueError(f"Marketing script field '{key}' must be a non-empty string.")
    return value.strip()
def _ss(data:Mapping[str,object],key:str)->tuple[str,...]:
    value=data.get(key)
    if not isinstance(value,list) or not value or not all(isinstance(x,str) and x.strip() for x in value): raise ValueError(f"Marketing script field '{key}' must be a non-empty list of strings.")
    return tuple(x.strip() for x in value)
class ScriptAgent:
    def __init__(self,generator:StructuredGenerator)->None: self.generator=generator
    def generate_script(self,brief:CampaignBrief)->MarketingScript:
        facts={"product_name":brief.product_name,"category":brief.category,"features":brief.features,"benefits":brief.benefits,"target_audience":brief.target_audience,"marketing_goal":brief.marketing_goal,"brand_tone":brief.brand_tone,"selling_points":brief.selling_points,"emotional_angle":brief.emotional_angle}
        data=self.generator.generate("Write one factual Radboards Instagram Reel script lasting 15 to 45 seconds. Use only this campaign brief; do not add unverified claims, pricing, or promotions.\n\nCAMPAIGN BRIEF:\n"+json.dumps(facts),SCHEMA)
        duration=data.get("estimated_duration_seconds")
        if not isinstance(duration,int) or not 15<=duration<=45: raise ValueError("Script duration must be an integer between 15 and 45 seconds.")
        return MarketingScript(_s(data,"hook"),_s(data,"voiceover"),_ss(data,"on_screen_text"),_s(data,"call_to_action"),duration)