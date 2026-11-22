export interface ArchitecturalHotspot {
  id: string;
  title: string;
  category: string;
  metrics: string[];
  description: string;
  position: [number, number, number];
  cameraTarget: [number, number, number];
  flyMode?: boolean;
}

export const ARCHITECTURAL_HOTSPOTS: ArchitecturalHotspot[] = [
  {
    id: 'jesus-tower',
    title: 'Turm Jesu Christi (172,5 m)',
    category: 'Zentralturm',
    metrics: ['Höhe: 172,5 m', 'Kreuz: 17 m (vierarmig)', 'Aussichtsgalerie: 136 m'],
    description:
      'Der höchste der 18 Türme erhebt sich über der Vierung und macht die Sagrada Família zur höchsten Kirche der Welt. Seine 172,5 m bleiben bewusst knapp unter dem 177 m hohen Hausberg Montjuïc – Gaudí wollte kein Menschenwerk über die Schöpfung Gottes erheben. Das 17 m hohe vierarmige Kreuz aus Keramik und Glas ist von allen Seiten als Kreuz erkennbar.',
    position: [0, 156, 0],
    cameraTarget: [55, 142, 55],
    flyMode: true,
  },
  {
    id: 'mary-star',
    title: 'Turm der Jungfrau Maria & Morgenstern',
    category: 'Apsisturm',
    metrics: ['Höhe: 138,0 m', 'Stern-Ø: 7,5 m', '12 Kristallzacken'],
    description:
      'Über der Apsis krönt der beleuchtete zwölfzackige Morgenstern den 138 m hohen Marien-Turm. Der Turmschaft folgt einem sich nach oben verjüngenden Hyperboloid mit blau-weißem Trencadís-Mosaik. Nachts erstrahlt der Stern weit über Barcelona.',
    position: [0, 134.2, -22.5],
    cameraTarget: [42, 126, -54],
    flyMode: true,
  },
  {
    id: 'evangelist-towers',
    title: 'Die vier Evangelisten-Türme',
    category: 'Zentralgruppe',
    metrics: ['Höhe: 135,0 m', 'Tetramorph-Skulpturen', '4 Türme um die Vierung'],
    description:
      'Vier 135 m hohe Türme umringen den Turm Jesu Christi und tragen die weißen, geflügelten Symbole des Tetramorphs: Löwe (Markus), Stier (Lukas), Adler (Johannes) und Engel (Matthäus). Sie ruhen statisch auf den vier roten Porphyr-Säulen der Vierung.',
    position: [11.5, 129, -11.5],
    cameraTarget: [45, 122, -45],
    flyMode: true,
  },
  {
    id: 'double-twisted-columns',
    title: 'Doppelt verdrehte Baum-Säulen',
    category: 'Gaudís Geometrie',
    metrics: ['Porphyr (12-eckig)', 'Basalt (10-eckig)', 'Granit (8-eckig)', 'Sandstein (6-eckig)'],
    description:
      'Gaudí entwickelte eine völlig neue Säulengeometrie: Zwei Polygone drehen sich gegenläufig nach oben und verschmelzen von einem sternförmigen Profil über die doppelte Kantenzahl bis zum perfekten Kreis am elliptischen Kapitell-Knoten. Die Gesteinsart richtet sich exakt nach der Traglast – vom roten Porphyr im Zentrum bis zum Montjuïc-Sandstein außen.',
    position: [7.5, 11.5, 7.5],
    cameraTarget: [0, 4.5, 20],
    flyMode: false,
  },
  {
    id: 'hyperboloid-vaults',
    title: 'Hyperboloid-Gewölbe & Lichtrosetten',
    category: 'Tragwerk & Licht',
    metrics: ['Seitenschiffe: 30 m', 'Hauptschiff: 45 m', 'Vierung: 60 m'],
    description:
      'Statt klassischer Kreuzrippengewölbe schuf Gaudí ein Dach aus ineinandergreifenden Hyperboloiden und Paraboloiden – doppelt gekrümmte Regelflächen, die komplett aus geraden Linien konstruierbar sind. Die vergoldeten Lichtöffnungen (Oculi) lassen Tageslicht wie durch ein Blätterdach ins Kirchenschiff fallen.',
    position: [0, 42.5, 18.75],
    cameraTarget: [0, 3.5, 28],
    flyMode: false,
  },
  {
    id: 'stained-glass-east',
    title: 'Buntglas Ost — Morgenlicht (Joan Vila-Grau)',
    category: 'Lichtkonzept',
    metrics: ['Kühle Palette: Blau → Türkis → Smaragd', 'Morgensonne 07:30–11:30'],
    description:
      'Die Ostfenster Richtung Geburtsfassade sind in kühlen Blau-, Türkis- und Grüntönen gestaltet und symbolisieren Wasser, Geburt und den Beginn des Lebens. Wenn die Morgensonne einfällt, taucht sie das gesamte Kirchenschiff in kühles, aquamarinfarbenes Licht.',
    position: [22.2, 11.0, 22.5],
    cameraTarget: [8, 3.0, 22.5],
    flyMode: false,
  },
  {
    id: 'stained-glass-west',
    title: 'Buntglas West — Abendlicht',
    category: 'Lichtkonzept',
    metrics: ['Warme Palette: Rubin → Orange → Gold', 'Abendsonne 15:00–19:30'],
    description:
      'Gegenüber auf der Passionsseite glühen die Fenster in tiefem Rubinrot, Orange und Gold – Symbol für Feuer, Passion und Sonnenuntergang. Verstelle den Tageszeit-Regler auf Abendrot, um das berühmte warme Farbspiel im Säulenwald zu erleben.',
    position: [-22.2, 11.0, 22.5],
    cameraTarget: [-8, 3.0, 22.5],
    flyMode: false,
  },
  {
    id: 'high-altar-baldachin',
    title: 'Hochaltar & Schwebender Baldachin',
    category: 'Liturgie',
    metrics: ['Porphyr-Altar', 'Sechseckiger Gold-Baldachin', '75 m Apsis-Lichtkuppel'],
    description:
      'Der Hauptaltar aus rotem Porphyr wird von Gaudís sechseckigem, schwebendem Baldachin überspannt, verziert mit Weinreben, Weizenähren und 50 Hängelampen. Darüber öffnet sich die Apsiskuppel in Richtung des Marien-Turms.',
    position: [0, 12.2, -18.0],
    cameraTarget: [0, 3.2, -4.0],
    flyMode: false,
  },
  {
    id: 'nativity-facade',
    title: 'Geburtsfassade & Lebensbaum-Zypresse',
    category: 'Ostfassade (UNESCO)',
    metrics: ['Erbaut: 1894–1930', '3 Portale: Hoffnung, Liebe, Glaube', 'Türme: 98,4–107 m'],
    description:
      'Die einzige noch weitgehend unter Gaudís direkter Leitung entstandene Fassade feiert die Geburt Christi in überbordender, organischer Natur-Skulptur. Zwischen den vier Türmen wächst die grüne Zypresse als Baum des Lebens, besetzt mit weißen Friedenstauben.',
    position: [34.0, 24.0, 0.0],
    cameraTarget: [64, 3.5, 4],
    flyMode: false,
  },
  {
    id: 'passion-facade',
    title: 'Passionsfassade & Knochensäulen',
    category: 'Westfassade',
    metrics: ['6 schräge Knochensäulen', 'Skulpturen: Josep M. Subirachs', 'Türme: 107,4–112,2 m'],
    description:
      'In bewusstem Kontrast zur üppigen Geburtsfassade wirkt die Westseite karg, kantig und dramatisch. Sechs gewaltige, nach innen geneigte Säulen erinnern an Sehnen und Knochen und tragen das scharf geschnittene Giebeldreieck im harten Licht der Abendsonne.',
    position: [-36.5, 16.0, 0.0],
    cameraTarget: [-58, 2.5, 4],
    flyMode: false,
  },
  {
    id: 'glory-facade',
    title: 'Glorienfassade & Große Freitreppe',
    category: 'Südfassade (Finaler Entwurf)',
    metrics: ['7 Laternensäulen', 'Türme bis 120 m', 'Monumentale Eingangsbrücke'],
    description:
      'Die geplante Hauptfassade im Süden ist der Herrlichkeit Gottes und dem Weg des Menschen gewidmet. Sieben hohe Säulen stehen für die sieben Gaben des Heiligen Geistes; eine große monumentale Freitreppe führt feierlich über die Carrer de Mallorca direkt ins 45 m hohe Hauptschiff.',
    position: [0, 20.0, 56.5],
    cameraTarget: [0, 2.8, 84],
    flyMode: false,
  },
  {
    id: 'gaudi-tomb',
    title: 'Krypta & Grab von Antoni Gaudí',
    category: 'Untergeschoss (-5,5 m)',
    metrics: ['Neugotisches Gewölbe', 'Beigesetzt: 12. Juni 1926', 'Kapelle Carmen'],
    description:
      'Unter der Apsis liegt die älteste fertiggestellte Ebene der Basilika (begonnen 1882 durch Francisco de Paula del Villar, vollendet von Gaudí). In der Kapelle Unserer Lieben Frau vom Berge Karmel befindet sich das schlichte Grab Antoni Gaudís.',
    position: [-9.8, -4.5, -23.5],
    cameraTarget: [-3.0, -3.7, -18.5],
    flyMode: false,
  },
  {
    id: 'cloister-sacristy',
    title: 'Umlaufender Kreuzgang & Sakristei-Kuppeln',
    category: 'Umgang & Nebengebäude',
    metrics: ['Sakristei-Höhe: 38 m', '12-eckige gedrehte Rippenkuppel', 'Schallpuffer zur Stadt'],
    description:
      'Anders als bei mittelalterlichen Kathedralen legte Gaudí den Kreuzgang als schützenden, begehbaren Umgang rund um die gesamte Basilika an – als akustischen Filter gegen den Straßenlärm Barcelonas. An den Nordecken krönen die 38 m hohen, gedrehten Sakristei-Kuppeln das Ensemble.',
    position: [27.5, 22.0, -32.5],
    cameraTarget: [46, 4.0, -48],
    flyMode: false,
  },
  {
    id: 'gaudi-chain-model',
    title: 'Gaudís Ketten-Hängemodell (Ausstellung)',
    category: 'Gaudí-Werkstatt',
    metrics: ['Umgekehrte Kettenlinie', 'Messingketten & Bleigewichte', 'Westliches Seitenschiff'],
    description:
      'Statt nur am Reißbrett zu rechnen, hing Antoni Gaudí feine Ketten mit kleinen Bleigewichten an die Decke: Die entstehenden Kurven (Kettenlinien / Katenoide) stehen rein unter Zug – auf den Kopf gestellt ergeben sie die statisch perfekte Druckbogen-Form für Säulen und Gewölbe.',
    position: [-18.6, 3.2, 39.5],
    cameraTarget: [-14.5, 2.9, 36.5],
    flyMode: false,
  },
  {
    id: 'baptistery-font',
    title: 'Taufbecken & Apsis-Kapellen',
    category: 'Liturgische Ausstattung',
    metrics: ['Achteckiges Porphyr-Becken', '7 Kerzen-Apsiskapellen', '18 Gaudí-Kronleuchter'],
    description:
      'Das achteckige Taufbecken aus poliertem rotem Porphyr unter einem goldenen Baldachin symbolisiert den achten Tag der Schöpfung. Rund um die Apsis laden sieben beleuchtete Opferkerzen-Kapellen mit Heiligenstatuen zur stillen Kontemplation ein.',
    position: [19.2, 3.2, 9.8],
    cameraTarget: [13.5, 2.9, 13.5],
    flyMode: false,
  },
  {
    id: 'eixample-pond',
    title: 'Plaça de Gaudí & Eixample-Stadtblock',
    category: 'Städtebau Barcelona',
    metrics: ['Cerdà-Raster (45°-Ecken)', 'Panot-Gehwegfliesen', 'Spiegelteich Ost'],
    description:
      'Die Basilika steht inmitten von Ildefons Cerdàs berühmtem Eixample-Raster mit seinen abgeschrägten Häuserecken (Chamfers) und den typischen „Flor de Barcelona“-Gehwegplatten. Der Parkteich auf der Plaça de Gaudí bietet das ikonische Spiegelbild der Geburtsfassade.',
    position: [82.5, 2.2, 0.0],
    cameraTarget: [104, 2.2, 6],
    flyMode: false,
  },
];
