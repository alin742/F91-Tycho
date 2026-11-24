# F91 Tycho – parts you buy yourself

Everything on the main board (chips, passives, connector, diodes) comes assembled from **JLCPCB** with the PCB order
(`Hardware/KiCad/panel/fab/`). This list is only what JLC does not supply. Checked 2026-11-24, delivery to Germany.
"Read" = product page opened; "snippet" = only the shop's text in search results (check price/stock yourself).

| What | Spec | Where | Price | Notes |
|---|---|---|---|---|
| Battery ×3 | LIR2016, 3.7 V, **1.6 mm thick** | [Rapid Online – Akyga AKY1983, 28 mAh](https://www.rapidonline.com/akyga-aky1983-rechargeable-button-cell-lir2016-28mah-li-ion-3-7v-13-6286) · [Akyga AKY1981, 22 mAh](https://www.rapidonline.com/akyga-aky1981-button-cell-rechargeable-lir2016-li-ion-22mah-3-7v-13-6285) | £5.38 / £4.17 each | Read, in stock. UK shop: check they ship lithium cells to DE. Alternative: [eBay.de 10× LIR2016](https://www.ebay.de/itm/283800888931) (snippet, thickness not listed – measure before use, must be ≤ 1.6 mm). |
| Charging cable | magnetic pogo, 2 pins, 2.5 mm pitch | [AliExpress – 2-pin 2.5 mm pair](https://www.aliexpress.us/item/3256805634338365.html) · [AliExpress – 2.5/2.6 mm](https://www.aliexpress.us/item/3256803324922674.html) · [Electrokit – 2-pin male 2.54 mm](https://www.electrokit.com/en/2-pin-male-magnetic-pogo-pin-connector-spring-loaded) · [LCSC C41361289 (Samzo PR5L5015-2P-C-H)](https://www.lcsc.com/product-detail/C41361289.html) | ~$1–3 | Snippet/read. Its magnets have nothing to grip any more (no magnets in the watch): hold the cable on, or use a cradle. 2.5 or 2.54 mm pitch both reach the pins (Ø1.2 pins in Ø1.8 holes). |
| Contact pins | brass rod **Ø1.2 mm** (2 pieces of ~5 mm needed) | QUARKZMAN H62 brass rod 1.2 × 203 mm, 12 pcs (Amazon) | – | Your find. Soldered in the two plated holes, 1.85 mm below the board (flush with the back’s inner face), tips tinned. |
| Hole sealant / insulation | MS-polymer | [Soudal Fix ALL Flexi – Hornbach](https://www.hornbach.de/p/soudal-fix-all-flexi-montagekleber-schwarz-470-g/7635733/) · [baustoffshop.de](https://www.baustoffshop.de/soudal-fix-all-classic-hybrid-kleb-dichtstoff-290-ml.html) | ~€13 | Snippet. Bead around each pin inside the back: seals water and keeps the pins off the steel. |
| Kapton tape | polyimide, ~0.05 mm | [iFixit DE (thickness not stated)](https://www.ifixit.com/de-de/products/polyimide-tape) · [eBay.de 0.05 mm](https://www.ebay.de/itm/254756991839) | €10 | Read/snippet. Wrap on the pins (fits the 0.3 mm gap) and under the battery. |
| Drill for the back | **Ø1.8 mm**, HSS-E / cobalt (stainless) | [Hoffmann GARANT 114580 Ø1.8](https://www.hoffmann-group.com/AT/de/hoa/p/114580-1%2C8) · [eBay.de HSS-E Co5 (1.6 shown)](https://www.ebay.de/itm/276885397747) | €9 / €2.40 | Read/snippet. Two holes in the steel back. |
| Spare case back / watch | Casio F-91W | [eBay.de case back NOS](https://www.ebay.de/itm/285935344192) · complete F-91W-1YER ≈ €22–25 (Amazon.de) | – | Snippet. Practise the holes on a spare. |
| OLED | ER-OLED0.83-1W, 0.83" 96×39, SSD1306 | [buydisplay](https://www.buydisplay.com/96x39-pixel-0-83-inch-small-oled-display-manufacturers-i2c-serial-spi) | $3.54 | Snippet, listed in stock. |
| Programmer | TI XDS110 (TMDSEMU110-U) | [DigiKey.de](https://www.digikey.de/en/products/detail/texas-instruments/TMDSEMU110-U/7104516) | €254 | **Out of stock until ~Feb 2027.** Use the XDS110 on any TI LaunchPad instead (cheaper, in stock). |

No longer needed (old charging-PCB design): magnets, FFC ribbon, rubber sheet, E6000.
