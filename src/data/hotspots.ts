import type { Localized } from '../i18n';

export interface ArchitecturalHotspot {
  id: string;
  title: Localized;
  category: Localized;
  metrics: Localized<string[]>;
  description: Localized;
  position: [number, number, number];
  cameraTarget: [number, number, number];
  flyMode?: boolean;
}

export const ARCHITECTURAL_HOTSPOTS: ArchitecturalHotspot[] = [
  {
    id: 'jesus-tower',
    title: { de: 'Turm Jesu Christi (172,5 m)', en: 'Tower of Jesus Christ (172.5 m)' },
    category: { de: 'Zentralturm', en: 'Central tower' },
    metrics: {
      de: ['Höhe: 172,5 m', 'Kreuz: 17 m (vierarmig)', 'Aussichtsgalerie: 136 m'],
      en: ['Height: 172.5 m', 'Cross: 17 m (four-armed)', 'Viewing gallery: 136 m'],
    },
    description: {
      de: 'Der höchste der 18 Türme erhebt sich über der Vierung und macht die Sagrada Família zur höchsten Kirche der Welt. Seine 172,5 m bleiben bewusst knapp unter dem 177 m hohen Hausberg Montjuïc – Gaudí wollte kein Menschenwerk über die Schöpfung Gottes erheben. Im hohlen Steinkern oberhalb des 60 m hohen Vierungsgewölbes fährt ein echter, aufgehängter Glas- und Edelstahl-Aufzug (umgeben von einer steinernen Wendeltreppe) hinauf unter das 17 m hohe vierarmige Kreuz.',
      en: "The tallest of the 18 towers rises above the crossing and makes the Sagrada Família the tallest church in the world. At 172.5 m it deliberately stops just short of Montjuïc, Barcelona's 177 m hill – Gaudí did not want a human work to rise above God's creation. Inside the hollow stone core, above the 60 m crossing vault, a real suspended glass-and-stainless-steel elevator (wrapped by a stone spiral staircase) climbs to just beneath the 17 m four-armed cross.",
    },
    position: [0, 156, 0],
    cameraTarget: [55, 142, 55],
    flyMode: true,
  },
  {
    id: 'mary-star',
    title: { de: 'Turm der Jungfrau Maria & Morgenstern', en: 'Tower of the Virgin Mary & Morning Star' },
    category: { de: 'Apsisturm', en: 'Apse tower' },
    metrics: {
      de: ['Höhe: 138,0 m', 'Stern-Ø: 7,5 m', '12 Kristallzacken'],
      en: ['Height: 138.0 m', 'Star Ø: 7.5 m', '12 crystal points'],
    },
    description: {
      de: 'Über der Apsis krönt der beleuchtete zwölfzackige Morgenstern den 138 m hohen Marien-Turm. Der Turmschaft folgt einem sich nach oben verjüngenden Hyperboloid mit blau-weißem Trencadís-Mosaik. Nachts erstrahlt der Stern weit über Barcelona.',
      en: 'Above the apse, the illuminated twelve-pointed Morning Star crowns the 138 m Tower of the Virgin Mary. The shaft follows a hyperboloid that tapers as it rises, clad in blue-and-white Trencadís mosaic. At night the star shines out far across Barcelona.',
    },
    position: [0, 134.2, -22.5],
    cameraTarget: [42, 126, -54],
    flyMode: true,
  },
  {
    id: 'evangelist-towers',
    title: { de: 'Die vier Evangelisten-Türme', en: 'The four Evangelist towers' },
    category: { de: 'Zentralgruppe', en: 'Central group' },
    metrics: {
      de: ['Höhe: 135,0 m', 'Tetramorph-Skulpturen', '4 Türme um die Vierung'],
      en: ['Height: 135.0 m', 'Tetramorph sculptures', '4 towers around the crossing'],
    },
    description: {
      de: 'Vier 135 m hohe Türme umringen den Turm Jesu Christi und tragen die weißen, geflügelten Symbole des Tetramorphs: Löwe (Markus), Stier (Lukas), Adler (Johannes) und Engel (Matthäus). Sie ruhen statisch auf den vier roten Porphyr-Säulen der Vierung.',
      en: 'Four 135 m towers ring the Tower of Jesus Christ, each crowned with a white, winged symbol of the tetramorph: the lion (Mark), the ox (Luke), the eagle (John) and the angel (Matthew). Structurally they bear on the four red porphyry columns of the crossing.',
    },
    position: [11.5, 129, -11.5],
    cameraTarget: [45, 122, -45],
    flyMode: true,
  },
  {
    id: 'double-twisted-columns',
    title: { de: 'Doppelt verdrehte Baum-Säulen', en: 'Double-twisted tree columns' },
    category: { de: 'Gaudís Geometrie', en: "Gaudí's geometry" },
    metrics: {
      de: ['Porphyr (12-eckig)', 'Basalt (10-eckig)', 'Granit (8-eckig)', 'Sandstein (6-eckig)'],
      en: ['Porphyry (12-sided)', 'Basalt (10-sided)', 'Granite (8-sided)', 'Sandstone (6-sided)'],
    },
    description: {
      de: 'Gaudí entwickelte eine völlig neue Säulengeometrie: Zwei Polygone drehen sich gegenläufig nach oben und verschmelzen von einem sternförmigen Profil über die doppelte Kantenzahl bis zum perfekten Kreis am elliptischen Kapitell-Knoten. Die Gesteinsart richtet sich exakt nach der Traglast – vom roten Porphyr im Zentrum bis zum Montjuïc-Sandstein außen.',
      en: 'Gaudí invented an entirely new column geometry: two polygons rotate in opposite directions as they rise, merging from a star-shaped profile through double the number of edges into a perfect circle at the elliptical capital knot. The choice of stone follows the load exactly – from red porphyry at the center to Montjuïc sandstone at the edges.',
    },
    position: [7.5, 11.5, 7.5],
    cameraTarget: [0, 4.5, 20],
    flyMode: false,
  },
  {
    id: 'hyperboloid-vaults',
    title: { de: 'Hyperboloid-Gewölbe & Lichtrosetten', en: 'Hyperboloid vaults & light rosettes' },
    category: { de: 'Tragwerk & Licht', en: 'Structure & light' },
    metrics: {
      de: ['Seitenschiffe: 30 m', 'Hauptschiff: 45 m', 'Vierung: 60 m'],
      en: ['Side aisles: 30 m', 'Nave: 45 m', 'Crossing: 60 m'],
    },
    description: {
      de: 'Statt klassischer Kreuzrippengewölbe schuf Gaudí ein Dach aus ineinandergreifenden Hyperboloiden und Paraboloiden – doppelt gekrümmte Regelflächen, die komplett aus geraden Linien konstruierbar sind. Die vergoldeten Lichtöffnungen (Oculi) lassen Tageslicht wie durch ein Blätterdach ins Kirchenschiff fallen.',
      en: 'Instead of classic ribbed cross vaults, Gaudí created a roof of interlocking hyperboloids and paraboloids – doubly curved ruled surfaces that can be built entirely from straight lines. Gilded openings (oculi) let daylight filter into the nave as if through a canopy of leaves.',
    },
    position: [0, 42.5, 18.75],
    cameraTarget: [0, 3.5, 28],
    flyMode: false,
  },
  {
    id: 'stained-glass-east',
    title: {
      de: 'Buntglas Ost — Morgenlicht (Joan Vila-Grau)',
      en: 'East stained glass — morning light (Joan Vila-Grau)',
    },
    category: { de: 'Lichtkonzept', en: 'Light concept' },
    metrics: {
      de: ['Kühle Palette: Blau → Türkis → Smaragd', 'Morgensonne 07:30–11:30'],
      en: ['Cool palette: blue → turquoise → emerald', 'Morning sun 07:30–11:30'],
    },
    description: {
      de: 'Die Ostfenster Richtung Geburtsfassade sind in kühlen Blau-, Türkis- und Grüntönen gestaltet und symbolisieren Wasser, Geburt und den Beginn des Lebens. Wenn die Morgensonne einfällt, taucht sie das gesamte Kirchenschiff in kühles, aquamarinfarbenes Licht.',
      en: 'The east windows, facing the Nativity façade, are composed in cool blues, turquoises and greens that stand for water, birth and the beginning of life. When the morning sun streams in, it bathes the whole nave in cool, aquamarine light.',
    },
    position: [22.2, 11.0, 22.5],
    cameraTarget: [8, 3.0, 22.5],
    flyMode: false,
  },
  {
    id: 'stained-glass-west',
    title: { de: 'Buntglas West — Abendlicht', en: 'West stained glass — evening light' },
    category: { de: 'Lichtkonzept', en: 'Light concept' },
    metrics: {
      de: ['Warme Palette: Rubin → Orange → Gold', 'Abendsonne 15:00–19:30'],
      en: ['Warm palette: ruby → orange → gold', 'Evening sun 15:00–19:30'],
    },
    description: {
      de: 'Gegenüber auf der Passionsseite glühen die Fenster in tiefem Rubinrot, Orange und Gold – Symbol für Feuer, Passion und Sonnenuntergang. Verstelle den Tageszeit-Regler auf Abendrot, um das berühmte warme Farbspiel im Säulenwald zu erleben.',
      en: 'Opposite, on the Passion side, the windows glow in deep ruby red, orange and gold – symbols of fire, the Passion and the setting sun. Move the time-of-day slider to sunset to see the famous play of warm color across the forest of columns.',
    },
    position: [-22.2, 11.0, 22.5],
    cameraTarget: [-8, 3.0, 22.5],
    flyMode: false,
  },
  {
    id: 'high-altar-baldachin',
    title: { de: 'Hochaltar & Schwebender Baldachin', en: 'High altar & floating baldachin' },
    category: { de: 'Liturgie', en: 'Liturgy' },
    metrics: {
      de: ['Porphyr-Altar', 'Sechseckiger Gold-Baldachin', '75 m Apsis-Lichtkuppel'],
      en: ['Porphyry altar', 'Hexagonal gold baldachin', '75 m apse lantern dome'],
    },
    description: {
      de: 'Der Hauptaltar aus rotem Porphyr wird von Gaudís sechseckigem, schwebendem Baldachin überspannt, verziert mit Weinreben, Weizenähren und 50 Hängelampen. Darüber öffnet sich die Apsiskuppel in Richtung des Marien-Turms.',
      en: "The main altar of red porphyry is spanned by Gaudí's hexagonal, floating baldachin, adorned with grapevines, ears of wheat and 50 hanging lamps. Above it, the apse dome opens up toward the Tower of the Virgin Mary.",
    },
    position: [0, 12.2, -18.0],
    cameraTarget: [0, 3.2, -4.0],
    flyMode: false,
  },
  {
    id: 'nativity-facade',
    title: { de: 'Geburtsfassade & Lebensbaum-Zypresse', en: 'Nativity façade & cypress Tree of Life' },
    category: { de: 'Ostfassade (UNESCO)', en: 'East façade (UNESCO)' },
    metrics: {
      de: ['Erbaut: 1894–1930', '3 Portale: Hoffnung, Liebe, Glaube', 'Türme: 98,4–107 m'],
      en: ['Built: 1894–1930', '3 portals: Hope, Charity, Faith', 'Towers: 98.4–107 m'],
    },
    description: {
      de: 'Die einzige noch weitgehend unter Gaudís direkter Leitung entstandene Fassade feiert die Geburt Christi in überbordender, organischer Natur-Skulptur. Zwischen den vier Türmen wächst die grüne Zypresse als Baum des Lebens, besetzt mit weißen Friedenstauben.',
      en: "The only façade built largely under Gaudí's own direction celebrates the birth of Christ in exuberant, organic sculpture drawn from nature. Between its four towers rises the green cypress, the Tree of Life, alighted upon by white doves of peace.",
    },
    position: [34.0, 24.0, 0.0],
    cameraTarget: [64, 3.5, 4],
    flyMode: false,
  },
  {
    id: 'passion-facade',
    title: { de: 'Passionsfassade & Knochensäulen', en: 'Passion façade & bone columns' },
    category: { de: 'Westfassade', en: 'West façade' },
    metrics: {
      de: ['6 schräge Knochensäulen', 'Skulpturen: Josep M. Subirachs', 'Türme: 107,4–112,2 m'],
      en: ['6 inclined bone-like columns', 'Sculpture: Josep M. Subirachs', 'Towers: 107.4–112.2 m'],
    },
    description: {
      de: 'In bewusstem Kontrast zur üppigen Geburtsfassade wirkt die Westseite karg, kantig und dramatisch. Sechs gewaltige, nach innen geneigte Säulen erinnern an Sehnen und Knochen und tragen das scharf geschnittene Giebeldreieck im harten Licht der Abendsonne.',
      en: 'In deliberate contrast to the lavish Nativity façade, the west side is stark, angular and dramatic. Six massive, inward-leaning columns evoke sinews and bones and carry the sharply cut triangular pediment in the hard light of the evening sun.',
    },
    position: [-36.5, 16.0, 0.0],
    cameraTarget: [-58, 2.5, 4],
    flyMode: false,
  },
  {
    id: 'glory-facade',
    title: { de: 'Glorienfassade & Große Freitreppe', en: 'Glory façade & grand staircase' },
    category: { de: 'Südfassade (Finaler Entwurf)', en: 'South façade (final design)' },
    metrics: {
      de: ['7 Laternensäulen', 'Türme bis 120 m', 'Monumentale Eingangsbrücke'],
      en: ['7 lantern columns', 'Towers up to 120 m', 'Monumental entrance bridge'],
    },
    description: {
      de: 'Die geplante Hauptfassade im Süden ist der Herrlichkeit Gottes und dem Weg des Menschen gewidmet. Sieben hohe Säulen stehen für die sieben Gaben des Heiligen Geistes; eine große monumentale Freitreppe führt feierlich über die Carrer de Mallorca direkt ins 45 m hohe Hauptschiff.',
      en: 'The planned main façade to the south is dedicated to the glory of God and the path of humankind. Seven tall columns stand for the seven gifts of the Holy Spirit; a grand, monumental staircase sweeps across Carrer de Mallorca straight into the 45 m nave.',
    },
    position: [0, 20.0, 56.5],
    cameraTarget: [0, 2.8, 84],
    flyMode: false,
  },
  {
    id: 'gaudi-tomb',
    title: { de: 'Krypta & Grab von Antoni Gaudí', en: 'Crypt & tomb of Antoni Gaudí' },
    category: { de: 'Untergeschoss (-5,5 m)', en: 'Lower level (-5.5 m)' },
    metrics: {
      de: ['Neugotisches Gewölbe', 'Beigesetzt: 12. Juni 1926', 'Kapelle Carmen'],
      en: ['Neo-Gothic vault', 'Laid to rest: 12 June 1926', 'Carmen chapel'],
    },
    description: {
      de: 'Unter der Apsis liegt die älteste fertiggestellte Ebene der Basilika (begonnen 1882 durch Francisco de Paula del Villar, vollendet von Gaudí). In der Kapelle Unserer Lieben Frau vom Berge Karmel befindet sich das schlichte Grab Antoni Gaudís.',
      en: "Beneath the apse lies the oldest completed level of the basilica, begun in 1882 by Francisco de Paula del Villar and finished by Gaudí. Antoni Gaudí's simple tomb rests in the Chapel of Our Lady of Mount Carmel.",
    },
    position: [-9.8, -4.5, -23.5],
    cameraTarget: [-3.0, -3.7, -18.5],
    flyMode: false,
  },
  {
    id: 'cloister-sacristy',
    title: {
      de: 'Umlaufender Kreuzgang & Sakristei-Kuppeln',
      en: 'Perimeter cloister & sacristy domes',
    },
    category: { de: 'Umgang & Nebengebäude', en: 'Ambulatory & outbuildings' },
    metrics: {
      de: ['Sakristei-Höhe: 38 m', '12-eckige gedrehte Rippenkuppel', 'Schallpuffer zur Stadt'],
      en: ['Sacristy height: 38 m', '12-sided twisted ribbed dome', 'Sound buffer against the city'],
    },
    description: {
      de: 'Anders als bei mittelalterlichen Kathedralen legte Gaudí den Kreuzgang als schützenden, begehbaren Umgang rund um die gesamte Basilika an – als akustischen Filter gegen den Straßenlärm Barcelonas. An den Nordecken krönen die 38 m hohen, gedrehten Sakristei-Kuppeln das Ensemble.',
      en: "Unlike in medieval cathedrals, Gaudí laid out the cloister as a sheltering walkway that runs all the way around the basilica – an acoustic filter against Barcelona's street noise. At the northern corners, the 38 m twisted sacristy domes crown the ensemble.",
    },
    position: [27.5, 22.0, -32.5],
    cameraTarget: [46, 4.0, -48],
    flyMode: false,
  },
  {
    id: 'gaudi-chain-model',
    title: {
      de: 'Gaudís Ketten-Hängemodell (Ausstellung)',
      en: "Gaudí's hanging chain model (exhibit)",
    },
    category: { de: 'Gaudí-Werkstatt', en: "Gaudí's workshop" },
    metrics: {
      de: ['Umgekehrte Kettenlinie', 'Messingketten & Bleigewichte', 'Westliches Seitenschiff'],
      en: ['Inverted catenary', 'Brass chains & lead weights', 'West side aisle'],
    },
    description: {
      de: 'Statt nur am Reißbrett zu rechnen, hing Antoni Gaudí feine Ketten mit kleinen Bleigewichten an die Decke: Die entstehenden Kurven (Kettenlinien / Katenoide) stehen rein unter Zug – auf den Kopf gestellt ergeben sie die statisch perfekte Druckbogen-Form für Säulen und Gewölbe.',
      en: 'Rather than relying on calculations at the drawing board alone, Antoni Gaudí hung fine chains weighted with small lead weights from the ceiling. The resulting curves (catenaries / catenoids) are in pure tension – turned upside down, they give the structurally ideal compression arch for columns and vaults.',
    },
    position: [-18.6, 3.2, 39.5],
    cameraTarget: [-14.5, 2.9, 36.5],
    flyMode: false,
  },
  {
    id: 'baptistery-font',
    title: { de: 'Taufbecken & Apsis-Kapellen', en: 'Baptismal font & apse chapels' },
    category: { de: 'Liturgische Ausstattung', en: 'Liturgical furnishings' },
    metrics: {
      de: ['Achteckiges Porphyr-Becken', '7 Kerzen-Apsiskapellen', '18 Gaudí-Kronleuchter'],
      en: ['Octagonal porphyry basin', '7 candlelit apse chapels', '18 Gaudí chandeliers'],
    },
    description: {
      de: 'Das achteckige Taufbecken aus poliertem rotem Porphyr unter einem goldenen Baldachin symbolisiert den achten Tag der Schöpfung. Rund um die Apsis laden sieben beleuchtete Opferkerzen-Kapellen mit Heiligenstatuen zur stillen Kontemplation ein.',
      en: 'The octagonal font of polished red porphyry beneath a golden baldachin symbolizes the eighth day of creation. Around the apse, seven candlelit votive chapels with statues of saints invite quiet contemplation.',
    },
    position: [19.2, 3.2, 9.8],
    cameraTarget: [13.5, 2.9, 13.5],
    flyMode: false,
  },
  {
    id: 'eixample-pond',
    title: { de: 'Plaça de Gaudí & Eixample-Stadtblock', en: 'Plaça de Gaudí & the Eixample block' },
    category: { de: 'Städtebau Barcelona', en: 'Barcelona urban planning' },
    metrics: {
      de: ['Cerdà-Raster (45°-Ecken)', 'Panot-Gehwegfliesen', 'Spiegelteich Ost'],
      en: ['Cerdà grid (45° corners)', 'Panot paving tiles', 'East reflecting pond'],
    },
    description: {
      de: 'Die Basilika steht inmitten von Ildefons Cerdàs berühmtem Eixample-Raster mit seinen abgeschrägten Häuserecken (Chamfers) und den typischen „Flor de Barcelona“-Gehwegplatten. Der Parkteich auf der Plaça de Gaudí bietet das ikonische Spiegelbild der Geburtsfassade.',
      en: "The basilica stands in the middle of Ildefons Cerdà's famous Eixample grid, with its chamfered street corners and the typical “Flor de Barcelona” paving tiles. The pond in the park on Plaça de Gaudí gives the iconic reflection of the Nativity façade.",
    },
    position: [82.5, 2.2, 0.0],
    cameraTarget: [104, 2.2, 6],
    flyMode: false,
  },
];
