#!/usr/bin/env python3
"""
Extract thread URLs from MCP webReader output for Tacoma World.
"""

import json
import re
from datetime import datetime
from pathlib import Path

# Thread URL pattern
THREAD_PATTERN = re.compile(r'/threads/([^.]+)\.(\d+)/')

# HTML content from successful MCP fetches
html_content_1st_gen = """1st Gen. Builds (1995-2004) | Tacoma World



### Log in or Sign up


![Image 1: Toyota Tacoma Forum](https://twstatic.net/data/mystuff/misc/header_left.png "Toyota Tacoma Forum")


![Image 2: Rest in Peace @EricL](https://twstatic.net/data/mystuff/misc/header-ericl.jpg?v=1 "Rest in Peace @EricL")



- Home


  - Recent Posts
  - Help

- Forums


  - Search Forums
  - Recent Posts

- Buy / Sell / Trade


  - Buy / Sell / Trade Rules
  - Buy / Sell Automotive
  - Buy / Sell Other
  - Group Buys
  - Deals & Coupons
  - Official Vendors

- Mods & Tutorials


  - Cheap Tacoma Mods
  - Largest tire sizes on stock suspension
  - Prevent Tailgate Theft Mod
  - Improve Gas Mileage
  - 2016 Oil Filter Location
  - DIY Oil Change
  - Oil Filter Comparisons
  - Washing & Detailing
  - 3rd Gen (2016+) How-To's
  - 2nd Gen (2005-2015) How-To's
  - 1st Gen (1995-2004) How-To's
  - Tire Size Calculator![Image 3](https://twstatic.net/data/mystuff/TireCalc/tire.gif)

  - Changing Spark Plugs
  - Check Engine Light OBD-2 Codes
  - Stereo Installation
  - Speaker Installation
  - Tacoma Towing Guide
  - Maintenance Req'd Light
  - Tire PSI
  - Remove Secondary Air Filter
  - Wiring After-Market Lights

- Media


  - The Gallery
  - Search Photos
  - TW Instagram
  - TW Live Thread



- Menu



Search


:   - Search titles only



Posted by Member:
:   Separate names with a comma.



Newer Than:




:   - Search this forum only
      - Display results as threads



:   ### Useful Searches

    - Recent Posts



    More...





__Tacoma World__





Home



Forums>



Tacoma Garage>



Builds>





1. ## Welcome to Tacoma World!



   You are currently viewing as a guest! To get full-access, you need to register for a FREE account.



   As a registered member, you'll be able to:


   - Participate in all Tacoma discussion topics


   - Communicate privately with other Tacoma owners from around the world


   - Post your own photos in our Members Gallery


   - Access all special features of the site



   Quick Links: ![Image 4](https://twstatic.net/data/threadthumbs/5/27/513921.jpg?v=1603157625)Prayn4surf ![Image 5](https://twstatic.net/data/threadthumbs/6/7c/663486.jpg?v=1603194377)2004 Long Travel Taco ![Image 6](https://twstatic.net/data/threadthumbs/6/72/667701.jpg?v=1603193788)Grimm's 04 Limited Build ![Image 7](https://twstatic.net/data/threadthumbs/6/0a/669972.jpg?v=1603193640)Djm228's maintenance thread ![Image 8](https://twstatic.net/data/threadthumbs/2/6a/297034.jpg?v=1603235672)4banger Junkyard build ![Image 9](https://twstatic.net/data/threadthumbs/4/22/449703.jpg?v=1603202158)MortalLove's '02 Build



# 1st Gen. Builds (1995-2004)



Build-up threads for 1st generation Tacomas



Post New Thread



Page 1 of 35



1


<


2



3



4



5



6



35



Next >



Sort by:


:   Title


    Start Date



:   Replies


    Views



:   Last Message ↓



1. ![Image 10](https://twstatic.net/data/threadthumbs/3/44/372874.jpg?v=1603210636)



   ### Otis24's Otisbound Outdoors Bodonkadonk Supercharged Twin Locked Micro Camper Build (OOBSTLMC)



   otis24,


   May 2, 2015



   ...



   47


   48


   49



   Replies:


   :   966



   Views:


   :   107,550



   otis24[OP]


   :   May 24, 2025 at 6:39 PM



2. ![Image 11](https://twstatic.net/data/threadthumbs/8/c8/850480.jpg?v=1736827621)



   ### Agent004 build



   Agent004,


   Jan 13, 2025



   ...

   2



   Replies:


   :   27



   Views:


   :   1,242



   Agent004[OP]


   :   May 24, 2025 at 4:01 PM



3. ![Image 12](https://twstatic.net/data/threadthumbs/5/21/565108.jpg?v=1728099063)



   ### Lefty's golden taco.



   chrslefty,


   Aug 25, 2018



   ...



   21


   22


   23



   Replies:


   :   456



   Views:


   :   31,194



   chrslefty[OP]


   :   May 23, 2025 at 9:32 PM



4. ![Image 13](https://twstatic.net/data/threadthumbs/7/43/788588.jpg?v=1737496221)



   ### 2004 Tacoma SAS



   dzuf,


   Jan 2, 2023



   ...



   8


   9


   10



   Replies:


   :   198



   Views:


   :   17,979



   dzuf[OP]


   :   May 23, 2025 at 5:29 PM



5. ![Image 14](https://twstatic.net/data/threadthumbs/8/3e/859087.jpg?v=1747893562)



   ### bones's righteously sinister 2004 tacoma ext cab build



   bigbadbilly,


   May 21, 2025 at 10:59 PM



   Replies:


   :   9



   Views:


   :   238



   bigbadbilly[OP]


   :   May 22, 2025 at 7:34 AM



6. ![Image 15](https://twstatic.net/data/threadthumbs/4/23/494372.jpg?v=1603200498)



   ### MadTaco Build



   Phessor,


   May 31, 2017



   ...



   39


   40


   41



   Replies:


   :   803



   Views:


   :   67,527



   Phessor[OP]


   :   May 20, 2025 at 6:16 PM



7. ![Image 16](https://twstatic.net/data/threadthumbs/8/c8/851409.jpg?v=1737999693)



   ### Jake's Lil' Baby Beast



   Tacofire98,


   Jan 27, 2025



   ...



   2



   Replies:


   :   25



   Views:


   :   1,296



   Tacofire98[OP]


   :   May 19, 2025 at 7:12 PM



8. ![Image 17](https://twstatic.net/data/threadthumbs/4/d6/484602.jpg?v=1611414046)



   ### AdventureTaco - turbodb's build and adventures



   turbodb,


   Apr 4, 2017



   ...



   274


   275


   276



   Replies:


   :   5,502



   Views:


   :   908,595



   turbodb[OP]


   :   May 19, 2025 at 1:36 PM



9. ![Image 18](https://twstatic.net/data/threadthumbs/5/62/579708.jpg?v=1645209602)



   ### Betterbuckleup's 2000 taco build & BS



   betterbuckleup,


   Nov 27, 2018



   ...



   45


   46


   47



   Replies:


   :   939



   Views:


   :   70,919



   betterbuckleup[OP]


   :   May 18, 2025 at 10:01 PM



10. ![Image 19](https://twstatic.net/data/threadthumbs/1/fc/182820.jpg?v=1609078742)



    ### Chris's Long Travel Supercharged do some of everything build



    atvlifestyle,


    Oct 16, 2011



   ...

    23


    24


    25



   Replies:


   :   486



   Views:


   :   62,365



   atvlifestyle[OP]


   :   May 18, 2025 at 4:16 PM



11. ![Image 20](https://twstatic.net/data/threadthumbs/8/f5/841348.jpg?v=1725335554)



    ### Not much Tacoma left.. 4500 koh build



    malburg114,


    Sep 2, 2024



   ...

    5


    6


    7



   Replies:


   :   136



   Views:


   :   6,433



   malburg114[OP]


   :   May 16, 2025



12. ![Image 21](https://twstatic.net/data/threadthumbs/7/87/786969.jpg?v=1671054471)



    ### Another Truck?! Third Time's the Charm TURBOCHARGED



    Speedytech7,


    Dec 14, 2022



   ...

    25


    26


    27



   Replies:


   :   526



   Views:


   :   24,457



    Speedytech7[OP]


   :   May 16, 2025



13. ![Image 22](https://twstatic.net/data/threadthumbs/4/56/475760.jpg?v=1682526801)



    ### Oliver the Lunar Mist Ext Cab Build, dual cased and double locked



    Dan8906,


    Feb 15, 2017



   ...

    23


    24


    25



   Replies:


   :   482



   Views:


   :   32,638



    Dan8906[OP]


   :   May 15, 2025



14. ![Image 23](https://twstatic.net/data/threadthumbs/3/75/350677.jpg?v=1603233947)



    ### The Supracharged King Ranch Bundle of Merriment Build



    TashcomerTexas,


    Nov 4, 2014



   ...

    30


    31


    32



   Replies:


   :   620



   Views:


   :   54,251



    TashcomerTexas[OP]


   :   May 13, 2025



15. ![Image 24](https://twstatic.net/data/threadthumbs/2/83/296319.jpg?v=1735696314)



    ### Taco Terror's '96 Old Truck Build



    taco terror,


    Sep 25, 2013



   ...

    3


    4


    5



   Replies:


   :   89



   Views:


   :   9,271



    taco terror[OP]


   :   May 11, 2025



16. ![Image 25](https://twstatic.net/data/threadthumbs/7/a7/723176.jpg?v=1622350466)



    ### Laxtoy's making of the pig



    Laxtoy,


    May 29, 2021



   ...

    2


    3



   Replies:


   :   47



   Views:


   :   2,559



    Laxtoy[OP]


   :   May 8, 2025



17. ![Image 26](https://twstatic.net/data/threadthumbs/7/7c/750854.jpg?v=1694546932)



    ### Little Red Turbo Creeper



    unstpible,


    Jan 10, 2022



   ...

    44


    45


    46



   Replies:


   :   900



   Views:


   :   40,775



    unstpible[OP]


   :   May 8, 2025



18. ![Image 27](https://twstatic.net/data/threadthumbs/3/e9/371416.jpg?v=1608496360)



    ### Snowy's 3-Linked 98 Xtra Cab



    Snowy,


    Apr 19, 2015



   ...

    25


    26


    27



   Replies:


   :   531



   Views:


   :   41,363



    Snowy[OP]


   :   May 8, 2025



19. ![Image 28](https://twstatic.net/data/threadthumbs/3/ef/300440.jpg?v=1605197049)



    ### Shortman build.



    Shortman5,


    Oct 27, 2013



   ...

    2



   Replies:


   :   32



   Views:


   :   6,475



    BlackSportD


   :   May 7, 2025



20. ![Image 29](https://twstatic.net/data/threadthumbs/3/00/373116.jpg?v=1603233004)



    ### Gray223's "The Resurrection" 98 rebuild build



    gray223,


    May 4, 2015



   ...

    13


    14


    15



   Replies:


   :   283



   Views:


   :   43,957



    gray223[OP]


   :   May 5, 2025



21. ![Image 30](https://twstatic.net/data/threadthumbs/5/16/596178.jpg?v=1728676831)



    ### Burt, The Old Man With friends Daryl and Donna



    CoWj,


    Feb 28, 2019



   ...

    21


    22


    23



   Replies:


   :   442



   Views:


   :   28,935



    CoWj[OP]


   :   May 5, 2025



22. ![Image 31](https://twstatic.net/data/threadthumbs/3/a9/304064.jpg?v=1603235427)



    ### StAndrew's Build



    StAndrew,


    Nov 23, 2013



   ...

    82


    83


    84



   Replies:


   :   1,669



   Views:


   :   131,702



    genuin1sequoia


   :   May 4, 2025



23. ![Image 32](https://twstatic.net/data/threadthumbs/5/13/531468.jpg?v=1746156973)



    ### Skeletoy's First Taco



    Skeletoy,


    Jan 30, 2018



   ...

    2


    3



   Replies:


   :   43



   Views:


   :   3,087



    4L27


   :   May 1, 2025



24. ![Image 33](https://twstatic.net/data/threadthumbs/6/f9/682272.jpg?v=1684850969)



    ### 1st Gen Taco/3rd Gen 4runner build



    mfior16,


    Aug 25, 2020



   Replies:


   :   16



   Views:


   :   4,775



    mfior16[OP]


   :   May 1, 2025



25. ![Image 34](https://twstatic.net/data/threadthumbs/1/bd/165208.jpg?v=1638957139)



    ### 04 Tacoma turned Buggy



    livel0veryde,


    Jul 4, 2011



   ...

    10


    11


    12



   Replies:


   :   231



   Views:


   :   49,787



    Broke Okie Ty


   :   May 1, 2025



26. ![Image 35](https://twstatic.net/data/threadthumbs/8/6d/857763.jpg?v=1746049268)



    ### Can someone pop my cherry?



    lil_coco,


    Apr 30, 2025



   Replies:


   :   2



   Views:


   :   134



    23MGM


   :   Apr 30, 2025



27. ![Image 36](https://twstatic.net/data/threadthumbs/8/e7/849681.jpg?v=1735855938)



    ### Daniel's Taco



    SpencerTacoSC,


    Jan 2, 2025



   Replies:


   :   10



   Views:


   :   545



    SpencerTacoSC[OP]


   :   Apr 30, 2025



28. ![Image 37](https://twstatic.net/data/threadthumbs/2/4a/261628.jpg?v=1603236608)



    ### Zam15's Adventure Build



    Zam15,


    Feb 4, 2013



   ...

    23


    24


    25



   Replies:


   :   483



   Views:


   :   71,569



    Zam15[OP]


   :   Apr 30, 2025



29. ![Image 38](https://twstatic.net/data/threadthumbs/7/1a/777527.jpg?v=1745859358)



    ### Bandido's 5lug Race Truck "Taquito"



    Bandido,


    Sep 8, 2022



   ...

    2



   Replies:


   :   30



   Views:


   :   2,223



    Bandido[OP]


   :   Apr 28, 2025



30. ![Image 39](https://twstatic.net/data/threadthumbs/4/93/437641.jpg?v=1745768657)



    ### Brice's NA V6 Build



    Brice,


    Jun 19, 2016



   ...

    104


    105


    106



   Replies:


   :   2,101



   Views:


   :   138,550



    Brice[OP]


   :   Apr 27, 2025



31. ![Image 40](https://twstatic.net/data/threadthumbs/5/10/518093.jpg?v=1736437891)



    ### Bandido's Bad at Taking Pictures '03 DC Build



    Bandido,


    Nov 3, 2017



   ...

    15


    16


    17



   Replies:


   :   321



   Views:


   :   23,042



    Bandido[OP]


   :   Apr 27, 2025



32. ![Image 41](https://twstatic.net/data/threadthumbs/6/f2/683473.jpg?v=1609208632)



    ### BimmerTim's Tacoma Build (tdi swap) and Trip Reports



    bimmertim,


    Sep 1, 2020



   ...

    3


    4


    5



   Replies:


   :   83



   Views:


   :   5,705



    bimmertim[OP]


   :   Apr 24, 2025



33. ![Image 42](https://twstatic.net/data/threadthumbs/2/4d/285648.jpg?v=1603235964)



    ### Fernando's 2004 DC! "THE TANK" Got Juanton Soup!



    Fernando,


    Jul 8, 2013



   ...

    151


    152


    153



   Replies:


   :   3,045



   Views:


   :   194,412



    crawlerjamie1


   :   Apr 23, 2025



34. ![Image 43](https://twstatic.net/data/threadthumbs/4/97/483207.jpg?v=1603163322)



    ### The Batoll Builds



    Fuergrissa,


    Mar 27, 2017



   ...

    32


    33


    34



   Replies:


   :   662



   Views:


   :   53,973



    Fuergrissa[OP]


   :   Apr 22, 2025



35. ![Image 44](https://twstatic.net/data/threadthumbs/6/10/653176.jpg?v=1605129908)



    ### 2003 DCSB Tacoma 1 Ton SAS



    AggiePE,


    Feb 18, 2020



   ...

    4


    5


    6



   Replies:


   :   111



   Views:


   :   9,896



    AggiePE[OP]


   :   Apr 21, 2025



36. ![Image 45](https://twstatic.net/data/threadthumbs/8/ef/853371.jpg?v=1740513197)



    ### Xtra_Taco's 1996 V6 4x4 5mt



    xtra_taco,


    Feb 25, 2025



   Replies:


   :   18



   Views:


   :   586



    xtra_taco[OP]


   :   Apr 21, 2025



37. ![Image 46](https://twstatic.net/data/threadthumbs/4/ad/435280.jpg?v=1603202674)



    ### boostedka's Turbo 3RZ Tacoma



    boostedka,


    Jun 3, 2016



   ...

    25


    26


    27



   Replies:


   :   522



   Views:


   :   128,912



    boostedka[OP]


   :   Apr 17, 2025



38. ### Stuck in accessory position



    Ghammer1495,


    Apr 17, 2025



   Replies:


   :   0



   Views:


   :   70



    Ghammer1495[OP]


   :   Apr 17, 2025



39. ![Image 47](https://twstatic.net/data/threadthumbs/8/bb/853712.jpg?v=1740935421)



    ### Classic Single Cab Build



    S.Beaty,


    Mar 2, 2025



   Replies:


   :   9



   Views:


   :   542



    Yetimetchkangmi


   :   Apr 16, 2025



40. ![Image 48](https://twstatic.net/data/threadthumbs/4/9d/415086.jpg?v=1629998659)



    ### First Gen IFS with Duals



    CedarPark,


    Feb 7, 2016



   ...

    13


    14


    15



   Replies:


   :   281



   Views:


   :   19,203



    02hilux


   :   Apr 11, 2025



41. ![Image 49](https://twstatic.net/data/threadthumbs/8/f0/824434.jpg?v=1725901439)



    ### Time623's 95 Taco Build and Trails



    time623,


    Feb 9, 2024



   ...

    2


    3



   Replies:


   :   48



   Views:


   :   3,166



    Supr4Lo


   :   Apr 11, 2025



42. ![Image 50](https://twstatic.net/data/threadthumbs/8/07/854108.jpg?v=1741395163)



    ### 2RZ Turbo Build. Saved from Rotting in the Woods.



    BeaverSmashing,


    Mar 7, 2025



   Replies:


   :   9



   Views:


   :   264



    Yetimetchkangmi


   :   Apr 9, 2025



43. ![Image 51](https://twstatic.net/data/threadthumbs/6/a8/648542.jpg?v=1603194842)



    ### 1998 Tacoma 5.3L Vortec (LS) Engine Swap Thread



    jimmy johnny,


    Jan 20, 2020



   ...

    7


    8


    9



   Replies:


   :   161



   Views:


   :   68,519



    drr


   :   Apr 6, 2025



44. ![Image 52](https://twstatic.net/data/threadthumbs/8/a6/855923.jpg?v=1743785034)



    ### Looking for battery disconnect switch mounting options



    Arctic Taco,


    Apr 2, 2025



   Replies:


   :   6



   Views:


   :   213



    Arctic Taco[OP]


   :   Apr 4, 2025



45. ![Image 53](https://twstatic.net/data/threadthumbs/6/0f/616428.jpg?v=1633303879)



    ### Frankenstein Build: Stock -> 37's on IFS -> SAS



    ForestRunnerFrank99,


    Jun 25, 2019



   ...

    19


    20


    21



   Replies:


   :   415



   Views:


   :   36,753



    ForestRunnerFrank99[OP]


   :   Apr 3, 2025



46. ![Image 54](https://twstatic.net/data/threadthumbs/8/14/856004.jpg?v=1743736255)



    ### Clutch spring bushings



    drewskie,


    Apr 3, 2025



   Replies:


   :   0



   Views:


   :   67



    drewskie[OP]


   :   Apr 3, 2025



47. ![Image 55](https://twstatic.net/data/threadthumbs/6/3f/637344.jpg?v=1720193714)



    ### My '79 Hilux Body Swapped First Gen Tacoma



    the_white_shadow,


    Nov 6, 2019



   ...

    2


    3


    4



   Replies:


   :   75



   Views:


   :   13,188



    the_white_shadow[OP]


   :   Apr 2, 2025



48. ![Image 56](https://twstatic.net/data/threadthumbs/8/3d/848624.jpg?v=1734387731)



    ### Boomtacoma's 86/96 build



    Boomtacoma01,


    Dec 16, 2024



   Replies:


   :   14



   Views:


   :   526



    Boomtacoma01[OP]


   :   Apr 2, 2025



49. ![Image 57](https://twstatic.net/data/threadthumbs/3/b7/375087.jpg?v=1603245115)



    ### Mlcc 02 DC build thread



    mlcc,


    May 21, 2015



   ...

    12


    13


    14



   Replies:


   :   263



   Views:


   :   24,592



    mlcc[OP]


   :   Mar 30, 2025



50. ![Image 58](https://twstatic.net/data/threadthumbs/5/ce/557220.jpg?v=1736823660)



    ### Spoonman's Little Tacoma



    Spoonman,


    Jul 5, 2018



   ...

    66


    67


    68



   Replies:


   :   1,346



   Views:


   :   114,829



    crawlerjamie1


   :   Mar 29, 2025




Showing threads 1 to 50 of 1,744



### Thread Display Options



Sort threads by:



Last message time


Thread creation time


Title (alphabetical)


Number of replies


Number of views


First message likes



Order threads in:



Descending order


Ascending order



Loading...



Post New Thread



Show Ignored Content



Page 1 of 35



1


<


2



3



4



5



6



35



Next >



### Products Discussed in



Entire Site


Forum: 1st Gen. Builds (1995-2004)"""



def extract_urls_from_content(html_content: str) -> set:
    """Extract thread URLs from HTML content."""
    urls = set()
    matches = THREAD_PATTERN.findall(html_content)

    for slug, thread_id in matches:
        url = f"https://www.tacomaworld.com/threads/{slug}.{thread_id}/"
        urls.add(url)

    return urls


def main():
    """Extract and save URLs."""
    print("Extracting thread URLs from Tacoma World content...")

    # Extract URLs from 1st Gen content
    urls_1st_gen = extract_urls_from_content(html_content_1st_gen)
    print(f"Found {len(urls_1st_gen)} URLs from 1st Gen Builds (first page)")

    # For now, we only have the first page of each forum
    # The site blocks pagination, so we can only access the first page
    all_urls = set()

    # Add URLs from 1st Gen (we have the content)
    all_urls.update(urls_1st_gen)

    # We would need to fetch 2nd Gen and 3rd Gen first pages too
    # For now, let's save what we have

    # Save to output file
    output_file = Path("/Users/core/MOTORMIA/Documents-data/GitHub/RalphOS/scraped_builds/tacoma_world_builds/urls.json")

    # Load existing URLs if any
    if output_file.exists():
        with open(output_file, 'r') as f:
            existing_data = json.load(f)
            existing_urls = set(existing_data.get('urls', []))
    else:
        existing_urls = set()

    # Combine URLs
    all_urls.update(existing_urls)

    # Save
    data = {
        'urls': sorted(list(all_urls)),
        'totalCount': len(all_urls),
        'lastUpdated': datetime.utcnow().isoformat() + 'Z',
        'note': 'Only first page of each forum accessible. Pagination is blocked by Tacoma World.'
    }

    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"\nTotal unique URLs: {len(all_urls)}")
    print(f"Saved to: {output_file}")
    print("\nIMPORTANT: Tacoma World blocks paginated URLs (page-2, page-3, etc.)")
    print("Only the first page of each forum section is accessible via MCP webReader.")
    print("Expected total if all pages were accessible: ~7,854 threads")
    print(f"Actual threads discovered (first pages only): {len(all_urls)}")


if __name__ == '__main__':
    main()
