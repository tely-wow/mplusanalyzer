import streamlit as st
import requests
from bs4 import BeautifulSoup, Comment
import json
import re
import pandas as pd

st.set_page_config(page_title="WoW M+ Run Analyzer", layout="wide")

def get_topruns(dungeon_name, desired_class, desired_spec):
    runswithclass = []
    base_url = "https://raider.io/api/v1/mythic-plus/runs"
    page = 0
    min_results = 10
    max_pages = 10

    with st.spinner('Fetching top runs...'):
        while len(runswithclass) < min_results and page < max_pages:
            runs_url = f"{base_url}?season=season-tww-1&region=world&page={page}"
            if dungeon_name:
                runs_url += f"&dungeon={dungeon_name}"
            
            try:
                response = requests.get(url=runs_url)
                response.raise_for_status()
                topruns = response.json()
            except requests.exceptions.RequestException as e:
                st.error(f"An error occurred: {e}")
                return []

            if "rankings" in topruns:
                for ranking in topruns["rankings"]:
                    run = ranking.get("run", {})
                    roster = run.get("roster", [])

                    for player in roster:
                        player_class = player.get("character", {}).get("class", {}).get("slug")
                        player_spec = player.get("character", {}).get("spec", {}).get("slug")
                        if player_class == desired_class and player_spec == desired_spec:
                            runswithclass.append(run.get("keystone_run_id"))
                            break

            page += 1

    return runswithclass

def get_run_details(run_id):
    base_url = f"https://raider.io/api/v1/mythic-plus/run-details?season=season-tww-1&id={run_id}"
    try:
        response = requests.get(url=base_url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"An error occurred while fetching run details: {e}")
        return None

def get_item_data(ench, gems, bonus, ilvl, itemid):
    # Convert bonus IDs to colon-separated string
    if isinstance(bonus, list):
        bonus_str = ':'.join(map(str, bonus))
    else:
        bonus_str = str(bonus)

    # Base URL with item ID and bonus IDs
    url = f"https://nether.wowhead.com/tooltip/item/{itemid}"
    if bonus_str:
        url += f"?bonus={bonus_str}"
    
    # Add remaining parameters
    params = {
        "ilvl": str(ilvl),
        "dataEnv": "1",
        "locale": "0"
    }
    
    # Only add gems and enchants if they exist
    if gems and any(gems):
        if isinstance(gems, list):
            params["gems"] = ':'.join(map(str, gems))
        else:
            params["gems"] = str(gems)
    
    if ench:
        params["ench"] = str(ench)
    
    print(f"Final URL: {url}")
    print(f"Params: {params}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0"
    }
    
    try:
        response = requests.get(url=url, headers=headers, params=params)
        print(f"Full URL with params: {response.url}")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching item data: {e}")
        return None

def extract_stats_from_html(tooltip_html, slot, gems):
    stats = {
        'versatility': 0,
        'crit': 0,
        'haste': 0,
        'mastery': 0
    }
    
    if not tooltip_html:
        return stats
        
    soup = BeautifulSoup(tooltip_html, 'html.parser')
    
    # Find all spans with class q2 (secondary stats)
    for span in soup.find_all('span', class_='q2'):
        text = span.get_text(strip=True)
        if text.startswith('+'):
            # Extract the number and stat type using regex
            match = re.match(r'\+<!--rtg\d+-->(\d+,?\d*)\s+(.+)', text)
            if not match:
                match = re.match(r'\+(\d+,?\d*)\s+(.+)', text)
            
            if match:
                # Remove commas and convert to integer
                value = int(match.group(1).replace(',', ''))
                stat_type = match.group(2).lower()
                
                # Map the stat types
                if 'critical strike' in stat_type:
                    stats['crit'] += value
                elif 'versatility' in stat_type:
                    stats['versatility'] += value
                elif 'haste' in stat_type:
                    stats['haste'] += value
                elif 'mastery' in stat_type:
                    stats['mastery'] += value
    
    print(f"Extracted stats: {stats}")  # Debug print
    return stats

def extract_gems_and_enchants(tooltip_html):
    if not tooltip_html:
        return [], "None"
        
    soup = BeautifulSoup(tooltip_html, 'html.parser')
    gems = []
    enchant = "None"

    # Look for gem sockets
    socket_spans = soup.find_all('span', string=re.compile(r'Socket'))
    for span in socket_spans:
        gems.append(span.get_text(strip=True))

    # Look for enchants
    enchant_pattern = re.compile(r'Enchanted:|Enhanced:')
    enchant_elements = soup.find_all(string=enchant_pattern)
    if enchant_elements:
        enchant = enchant_elements[0].strip()

    return gems, enchant

def main():
    st.title("WoW Mythic+ Run Analyzer")
    st.markdown("Analyze top Mythic+ runs for specific classes and specs")

    col1, col2, col3 = st.columns(3)
    
    with col1:
        dungeon = st.text_input("Dungeon Name (optional)", 
                               help="e.g., siege-of-boralus")
    
    with col2:
        desired_class = st.selectbox("Class", 
                                   ["mage", "warrior", "druid", "paladin", "hunter", "rogue", 
                                    "priest", "shaman", "warlock", "monk", "demon-hunter", "death-knight"])
    
    with col3:
        desired_spec = st.text_input("Specialization", 
                                   help="e.g., frost, arms, balance")

    if st.button("Analyze Runs"):
        if not desired_spec:
            st.error("Please enter a specialization")
            return

        run_ids = get_topruns(dungeon, desired_class, desired_spec)
        
        if not run_ids:
            st.warning("No runs found matching the criteria")
            return

        st.subheader(f"Found {len(run_ids)} runs matching your criteria")

        for run_id in run_ids:
            run_details = get_run_details(run_id)
            if run_details:
                with st.expander(f"Run ID: {run_id} - {run_details.get('dungeon', {}).get('name', 'N/A')} +{run_details.get('mythic_level', 'N/A')}"):
                    roster = run_details.get("roster", [])
                    total_stats = {
                        'versatility': 0,
                        'crit': 0,
                        'haste': 0,
                        'mastery': 0
                    }

                    for player in roster:
                        player_class = player.get("character", {}).get("class", {}).get("slug")
                        player_spec = player.get("character", {}).get("spec", {}).get("slug")
                        
                        if player_class == desired_class and player_spec == desired_spec:
                            items = player.get("items", {}).get("items", {})
                            talent_loadout = player.get("character", {}).get("talentLoadout", {}).get("loadoutText", "N/A")
                            
                            st.markdown(f"**Character:** {player.get('character', {}).get('name', 'Unknown')}")
                            st.markdown(f"**Talent Loadout:** `{talent_loadout}`")
                            st.markdown(f"**Raider.IO Profile:** [View Run](https://raider.io/mythic-plus-runs/season-tww-1/{run_id})")
                            
                            # Create a table for item stats
                            data = []
                            for slot, item in items.items():
                                if isinstance(item, dict):
                                    item_level = item.get("item_level", "N/A")
                                    item_name = item.get("name", "Unknown")
                                    item_id = str(item.get("item_id", ""))
                                    
                                    if item_id:
                                        try:
                                            # Get the raw item data
                                            enchant = item.get("enchant", "")
                                            gems = item.get("gems", [])
                                            bonuses = item.get("bonuses", [])
                                            
                                            item_tooltip = get_item_data(
                                                enchant,
                                                gems,
                                                bonuses,
                                                item_level,
                                                item_id
                                            )
                                            
                                            if item_tooltip and "tooltip" in item_tooltip:
                                                stats = extract_stats_from_html(item_tooltip["tooltip"], slot, item.get("gems", []))
                                                gems, enchant = extract_gems_and_enchants(item_tooltip["tooltip"])
                                                
                                                for stat, value in stats.items():
                                                    total_stats[stat] += value
                                                
                                                data.append([
                                                    slot, item_name, item_level,
                                                    ", ".join(gems) if gems else "None",
                                                    enchant,
                                                    stats["versatility"],
                                                    stats["crit"],
                                                    stats["haste"],
                                                    stats["mastery"]
                                                ])
                                                
                                        except Exception as e:
                                            st.error(f"Error processing item {item_name}: {str(e)}")
                            
                            if data:
                                df = pd.DataFrame(
                                    data,
                                    columns=["Slot", "Item Name", "Item Level", "Gems", "Enchant", 
                                            "Versatility", "Crit", "Haste", "Mastery"]
                                )
                                st.dataframe(df)
                                
                                st.markdown("### Total Stats")
                                st.markdown(f"""
                                - Versatility: {total_stats['versatility']}
                                - Critical Strike: {total_stats['crit']}
                                - Haste: {total_stats['haste']}
                                - Mastery: {total_stats['mastery']}
                                """)

if __name__ == "__main__":
    main()
