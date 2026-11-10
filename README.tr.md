<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/banner-tr-dark.svg">
    <img alt="Claude Code veya Codex liderliğinde agent-crew" src="docs/assets/banner-tr-light.svg" width="100%">
  </picture>
</p>

<p align="center">
  <a href="https://github.com/badblli/agent-crew/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/badblli/agent-crew/actions/workflows/ci.yml/badge.svg"></a>
  <a href="#claude-code-ile-kullanım"><img alt="Claude Code eklentisi" src="https://img.shields.io/badge/Claude%20Code-plugin-d97757"></a>
  <a href="#codex-ile-kullanım"><img alt="Codex eklentisi" src="https://img.shields.io/badge/Codex-plugin-10a37f"></a>
  <a href="LICENSE"><img alt="Lisans: MIT" src="https://img.shields.io/badge/license-MIT-blue"></a>
  <br>
  <a href="README.md">English</a> · <b>Türkçe</b>
</p>

**Kodlama ajanlarından oluşan ekibine Claude Code veya Codex liderlik etsin.**

Lider işi paketlere böler, her paketi ayrı bir Git worktree'sinde çalışan Claude Code veya Codex
ajanına verir, değişiklikleri inceler, testleri yeniden çalıştırır ve PR açar. İstersen Antigravity
CLI üzerinden Gemini ajanı da kullanabilirsin. Claude Code'da canlı pano ve karar bandı bulunur.
Codex panoyu ve karar sorularını sohbette gösterir, CI geçtikten sonra her PR için birleştirme onayı ister.

> Durum: erken aşama, her gün gerçek bir projede kullanılıyor. Windows + Git Bash ile test edildi;
> macOS/Linux'ta çalışması beklenir (bash, git, python, gh) ama henüz test edilmedi.

<p align="center">
  <img alt="Ekip panosu: takım bandı, adım çizgisi ve iş paketi, adım, motor ve canlı komutuyla üç ajan (demo veri)" src="docs/assets/board-preview-tr.svg" width="56%">
  &nbsp;
  <img alt="Kota paneli: Claude, Codex ve Gemini kullanım kadranları (demo veri)" src="docs/assets/quota-preview-tr.svg" width="40%">
  <br>
  <sub>Ekip panosu ve kota paneli, demo veriyle.</sub>
</p>

## 60 saniyede başla

1. Agent Crew'u [Claude Code](#claude-code-ile-kullanım) veya [Codex](#codex-ile-kullanım) için kur.
2. Bir proje aç ve *"bu projede ekibi kur"* de. `crew-init` lideri ve ajan motorlarını sorar,
   `.crew/` ile talimat dosyalarını yazar ve kurulum PR'ını açar.
3. Yeni bir oturum başlat. Claude Code'da paneller kendiliğinden açılır. Codex'te panoyu sohbette
   isteyebilir veya `python .crew/bin/board.py status` komutunu çalıştırabilirsin.
4. *"Rapor sayfasına CSV dışa aktarma ekle"* gibi bir iş iste. Lider kabul kriterleriyle iş
   paketini yazar, ajanları başlatır, değişiklikleri inceler ve PR açar.

## Nasıl çalışır

```mermaid
flowchart LR
  you([Sen<br/>ürün sahibi]) -->|istek| lead[Claude Code veya Codex<br/>teknik lider]
  lead -->|yazar| wp[İş paketi<br/>.crew/plan/wp/*.md]
  wp -->|.crew/bin/run-wp.sh| w1[Claude / Codex / Gemini ajanı<br/>kendi worktree'si, git yazmaz]
  w1 -->|olaylar, rapor| state[(.crew/state)]
  state --> board[Claude Code panelleri veya Codex sohbet panosu]
  w1 -->|diff| review{Lider inceler<br/>ve yeniden test eder}
  review -->|değişiklik iste| w1
  review -->|onay| ship[Commit · PR · CI]
  lead -.->|kritik karar| decision[Karar bandı veya sohbet] -.-> you
```

## Neler var

- **Üç Claude Code paneli**, oturum başında açılır:
  - **Ekip panosu** (`/crew`, Türkçe projelerde `/ekip`): faz, yol haritası ilerlemesi, her ajanın iş
    paketi, adımı, modeli, token kullanımı ve canlı "şimdi" satırı (çalıştırdığı komut ya da düzenlediği dosya).
  - **Ajanlar** (`/crew-agents`, `/ajanlar`): sekmelerle tüm ajanlara göz atılan tek panel (1–9, `p`/`n`
    tuşları): adım çizgisi, canlı komutlar ve düzenlemeler, renkli diff görüntüleyici ve lider, ajan ve
    sen arasındaki konuşma. Bir ajana not gönder; not önce lidere gider.
  - **Kota** (`/quota`, `/kota`): Claude plan pencereleri ve bağlam, Codex 5 saatlik ve haftalık
    limitler, bugünkü Gemini token'ları; bir motor %90'ı geçince bildirim.
  Masaüstü ve mobilde paneller SVG kadranlar, adım çizgisi ve takım bandı çizer; terminalde renkli
  metin çubukları görünür.
- **Kararlar ve ekip durumu** Claude Code'da karar bandı ve panellerde, Codex'te sohbette görünür.
- **Model yönlendirme**: her iş paketi bir seviye belirtir (light / standard / deep / peak); inceleme
  turları aynı ajan thread'ini aynı modelle sürdürür, önbellekteki prompt yeniden kullanılır.
- **Lider ve ajan seçimi**. Crew-init seçimini `.crew/config.json` dosyasında `lead` ve `engines`
  alanlarına yazar. İş paketi başına `- Engine: claude|codex|agy` (veya `CREW_ENGINE`) kullan.
  İkisi de yoksa atanan ajanın etkin motoru, o da yoksa ilk yapılandırılmış motor kullanılır.
  Bir motor kullanım limitine takılınca koşu sıfırlanma zamanıyla *paused* olarak işaretlenir;
  `CREW_FAILOVER=claude|agy|codex` ile iş aynı worktree'de diğer motorda devam eder.
- **Görünür Claude ajanları**: her oturumun adı `<ajan> · <wp>`. Ajan sohbetinde
  `open: claude --resume <session_id>` bulunur; tell.sh inceleme geri bildirimi için o oturumu sürdürür.
  `CREW_CLAUDE_BG=1` bunun yerine `claude agents` listesinde görünen bir oturum başlatır;
  `claude attach "<ajan> · <wp>"` ile izlenir. Arka plan modu yalnızca başlatmayı izler; lider oturumu
  kontrol ettikten sonra durdu olarak kaydeder, akan rapor/sohbet olmaz. Geri bildirim için attach kullan.
  `CREW_CLAUDE_PERMISSION_MODE` ajan izin modunu değiştirir (varsayılan `auto`), sürdürülen ve arka
  plan oturumları dahil. `acceptEdits` tek başına başsız (headless) Bash test komutlarına izin vermez.
- **İş paketi yaşam döngüsü**: teslim edilen WP'ler aynı PR içinde `wp/done/YYYY-MM/` altına arşivlenir;
  yerel `plan.md` yalnızca aktif işi gösterir, `history.md` merge'leri kaydeder ve kısa bir devir kartı
  sonraki lider oturumunun kaldığı yerden devam etmesini sağlar.
- **İkinci görüş (isteğe bağlı)**: `jev_route.py` TypeSafe'in Jev'ine motor, seviye, risk ve kullanıcının
  karar vermesi gerekip gerekmediğini sorar. Yalnızca açıkça etkinleştirildiğinde, iş paketi başına tek
  istek. İş paketinin başlığını, özetini, hedefini, görevlerini ve kabul kriterlerini TypeSafe'e gönderir.
- **Temalar**: Classic (varsayılan), Creature Tamer (savaş diyaloğu biçiminde karar bandı), Arcade Maze,
  Fantasy. Ajan id'leri hiç değişmez; tema değiştirmek tek satır.
- **İki skill**. `crew-init` projeyi kurar. `crew-lead` planlama, ajanları çalıştırma, inceleme
  ve teslim adımlarını tarif eder.

## Kurulum

Her iki istemci için Git, GitHub CLI (`gh`), Python 3 ve Bash gerekir. İsteğe bağlı olarak Gemini
ajanları için Antigravity CLI (`agy`), Jev yönlendirmesi için `TYPESAFE_API_KEY` kullanabilirsin.
Antigravity izinleri `~/.gemini/antigravity-cli/settings.json` dosyasından ayarlanır.

### Claude Code ile kullanım

```text
/plugin marketplace add badblli/agent-crew
/plugin install agent-crew@agent-crew
```

Ardından bir projede: *"bu projede ekibi kur"* (`crew-init` çalışır). Pano, ajanlar ve kota panelleri
bir sonraki oturum başında açılır (Türkçe projelerde ayrıca `/ekip`, `/ajanlar`, `/kota`).

Eklenti hook'larını destekleyen bir Claude Code sürümü kullan. Codex ajanlarını çalıştıracaksan
Codex CLI'ı da kur ve hesabına giriş yap.

### Codex ile kullanım

1. `codex plugin marketplace add badblli/agent-crew` komutunu çalıştır, ardından Codex'te
   `/plugins` menüsünden **Agent Crew** eklentisini kur.
2. Yeni bir oturum aç ve `/hooks` menüsünde Agent Crew SessionStart hook'unu inceleyip onayla.
3. Codex'ten `crew-init` çalıştırmasını iste. Lider olarak Codex'i seç
   (`.crew/config.json` içinde `"lead": "codex"`) ve ajan motorlarını belirle. Yalnızca Codex
   kullanan ekipler için Codex CLI, Git, `gh`, Python 3 ve Bash gerekir.

Codex'te ekip panelleri, karar bandı ve güncelleme bildirimleri yoktur. Panoyu görmek için
`python .crew/bin/board.py status` komutunu kullan. Karar ve PR birleştirme isteklerini sohbette yanıtla.

Güncellemek için `codex plugin marketplace upgrade agent-crew` komutunu çalıştır ve yeni bir Codex
oturumu aç. `/plugins` hâlâ eski sürümü gösteriyorsa Agent Crew eklentisini kaldırıp güncel
marketplace'ten yeniden kur. Onaylanan hook, projenin ekip script'lerini ve rollerini günceller.

## Claude Code eklentisini güncelleme

Bir ekip projesinde eklenti günde bir kez GitHub'da yeni sürüm olup olmadığına bakar ve varsa bildirim
gösterir: yayımlanmış `plugin.json` tek seferlik okunur, hiçbir şey gönderilmez. Eklentinin
*Check for updates* seçeneğiyle (`updateCheck`) kapatılabilir.

`/plugin update agent-crew@agent-crew`, ardından yeni bir oturum başlat. Oturum başında eklenti her ekip
projesinin `.crew/bin/` klasörünü kurulu sürüme getirir (`tools/sync_bin.py`) ve hangi dosyaların
değiştiğini söyler; bunları commit'le. Projede elle düzenlediğin bir script olduğu gibi bırakılır ve
bildirimde adı geçer. Bir ajan koşusu sürerken hiçbir şey değiştirilmez. Proje bazında kapatmak için
`.crew/config.json` içinde `"autoUpdate": false`, elle çalıştırmak için
`python <eklenti kökü>/tools/sync_bin.py --project .`.

`templates/bin/` içindeki bir script'i mi değiştiriyorsun? `python tools/sync_bin.py --record` çalıştır;
böylece kurulu projeler eski sürümü güvenle değiştirilebilir olarak tanır (CI bunu kontrol eder).

Worktree'ler varsayılan olarak ana checkout'un `node_modules` klasörünü bağlamaz.
`CREW_LINK_NODE_MODULES=1` ile bağlamak, bir ajanın bu paylaşılan klasörü değiştirmesine izin verir;
yalnızca bu erişimi kabul ediyorsan kullan. Lider, incelemeden sonra bağımlılığa dayalı kontrolleri ana
checkout'ta çalıştırabilir.

## Oluşturduğu proje düzeni

```text
.crew/config.json        proje, lang (en|tr), engines, lead, planDir, stateDir
.crew/plan/              team.json (kadro, adımlar, fazlar, temalar), models.json, wp/*.md
.crew/plan/wp/done/      teslim edilen WP'ler, teslim eden PR'da aya göre arşivlenir
.crew/plan/plan.md       aktif iş, üretilir (git-ignore); history.md ve history/ da öyle
.crew/plan/handoff.md    liderin oturum başında okuduğu kısa devir kartı
.crew/bin/               board.py, run-wp.sh, tell.sh, lib.sh, sync.sh, usage.py, jev_route.py
.crew/state/             pano, konuşmalar, koşular (git-ignore)
AGENTS.md                ortak sert kurallar ve rapor biçimi (en fazla 8 KB)
CLAUDE.md                1. satırda @AGENTS.md'yi içe aktarır; yalnızca Claude için lider notu
rule.md                  stack, doğrulanmış komutlar, mimari, sözleşmeler, kanıtlanmış dersler
feature.md               bir özellik → giriş dosyaları → testler tablosu
docs/adr/                kararlar, gerektiğinde bakılır
.claude/agents/          Claude için ekip rolleri (seçildiyse)
.codex/agents/           Codex için ekip rolleri (seçildiyse)
.crew/roles-rendered.json yerelde düzenlenmiş rolleri korumak için hash'ler
```

Her zaman yüklenen talimat çekirdeği kısa kalır. Ajanlar plan/history/handoff, notları ve tamamlanmış
WP arşivlerini yalnızca atanan WP bunlara bağlantı verirse okur; lider oturum başında yalnızca devir
kartını okur. Bilinmeyen proje ayrıntıları `unknown` olarak kalır.
Şablonlar İngilizce gelir; crew-init Türkçe projelerde başlıkları çevirir, yolları, config anahtarlarını
ve ortak final rapor biçimini korur.

Yerel rol tanımlarını tek kaynaktan yeniden üretmek için
`python <eklenti kökü>/tools/render_roles.py --project . --engines claude,codex`
(ya da yalnızca `claude` / `codex`). Projenin model seviyelerini okur, yerelde düzenlenmiş dosyaları
bildirir ve onlara dokunmaz. Codex özel ajan tanımları kendilerini başlatmaz ve üst sandbox/onay
yapılandırmasını geçersiz kılmaz. Depo düzeyindeki Codex skill'leri `.agents/skills/` altına konur.

Claude Code'da lider oturumuna bir kez `/rename <proje> lead` ile ad ver. Tam WP'ler runner'ı kullanır; liderin Agent
aracı yalnızca küçük, salt okunur yardımcılar içindir. Codex koşuları `workspace-write` kullanır; Claude
ajanları varsayılan olarak `--permission-mode auto` kullanır ve aynı "git yazma yok" ekip kurallarına uyar.
Ajan Claude rate-limit ipuçları koşu/durum dosyalarında saklanır; bir limit aşıldığında ya da durum
`allowed` olmadığında sohbete koşu başına en fazla bir uyarı düşer. Kota panelindeki Claude hesap
pencereleri lider oturumundan gelir. Panonun oturum komutu ajan sohbetinde bulunur; ayrı pano oturumu ve
ajan kotası widget'ları hook desteği gerektirir.

Kurulan ekip, hedef projede projeye özel WP'ler ve yerel koşu kayıtları oluşturur. WP'leri commit'lemeden
önce gözden geçir; `.crew/state/` ve `.env*` dosyalarını Git dışında tut. Eklentideki test fixture'ları,
kaydedilmiş ajan konuşmaları yerine sentetik olaylar kullanmalıdır.

## Reiss ile tanış

<img align="right" alt="agent-crew maskotu Reiss: kaptan şapkalı, elinde anahtar, büyüteç, pull request bayrağı ve test tüpü tutan bir ahtapot" src="docs/assets/mascot.svg" width="150">

Reiss (adı Türkçe *reis*ten geliyor) ekibi bir arada tutar: paralel ajanlar için sekiz kol, her biri iş başında: anahtar, büyüteç, test
tüpü ya da pull request bayrağı. `docs/assets/` içindeki görseller oradaki `make_brand.py` ve
`make_previews.py` ile üretilir; reponun geri kalanı gibi MIT lisanslıdır.

<br clear="right">

## Lisans

MIT
