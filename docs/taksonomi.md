# Hata Taksonomisi ve Etiketleme Kılavuzu

> **Bu belge projenin tek ortak spesifikasyonudur.**
> `src/generator.py` (üreteç) ve `src/verifier.py` (doğrulayıcı) bu belgeyi ayrı ayrı,
> birbirinden bağımsız olarak uygular. İkisi arasında **kod paylaşımı yasaktır**
> (bkz. `tests/test_independence.py`). Ortak olan spesifikasyondur, kod değildir.

Sürüm: 0.2 · Kapsam: 9–10. sınıf üçgenler kazanımları, hesaplama tipi problemler

---

## 1. Temel ayrım: çizim bağlayıcı değildir

Sistemin tamamı tek bir varsayıma dayanır:

> **`figure` bloğunda listelenmeyen hiçbir ilişki "verilmiş" sayılmaz.**

Bu, *kapalı dünya* varsayımıdır. Listede olmayan bir ilişki **yanlış** değil,
**bilinmiyor** demektir. Öğrenci bilinmeyeni kullanırsa hata yapmış olur.

Ders kitaplarındaki şekiller ölçekli değildir: kenara "7" yazılır ama 7 birim
çizilmez, 60°'lik açı 80° görünebilir. Sistem bu davranışı bilinçli olarak taklit
eder (`rendering.bias`). Bu nedenle **çizimden okunan hiçbir bilgi geçerli girdi değildir**.

---

## 2. Sınıflar

Dört sınıf vardır: üç hata sınıfı ve bir kontrol sınıfı. Her çözüme **tek bir sınıf**
ve **tek bir hatalı adım** atanır (bkz. §4).

### H0 — Hatasız

Çözümün tüm adımları geçerlidir: her adımda kullanılan teoremin ön koşulları,
`figure` bloğundaki verilenler veya önceki geçerli adımlar tarafından sağlanmaktadır.

- `error_step`: `null`
- Derlemin **~%25'i** bu sınıftan olmalıdır.
- Gerekçe: H0 örnekleri olmadan yanlış pozitif oranı ölçülemez. Her girdide hata
  bulan bir sistem, hiç hata bulmayan bir sistem kadar işe yaramazdır.

---

### H1 — Şekle Aşırı Güvenme

Öğrenci, çizimde *görünen* ancak `figure` bloğunda *bulunmayan* bir ilişkiyi doğru kabul eder.

**Tespit kuralı**
Bir adımın dayandığı öznitelik `figure` bloğunda yoksa **ve** öğrenci onu
`"rule": "verilen"` diyerek ya da örtük olarak kullanıyorsa → H1.

**Biçimsel tanım**
Akıl yürütme grafındaki bir kenar, şekil grafında bulunmayan bir özniteliğe dayanıyor.

**Tipik biçimler**
- Dik görünen açıyı 90° sayma *(P3 — kanonik)*
- Eşit görünen kenarları eşit sayma, üçgeni ikizkenar varsayma *(P2)*
- Yükseklik ayağı ile kenar orta noktasını aynı nokta sanma *(P5)*
- Çizimde paralel görünen doğruları paralel sayma

**Örnek**
```
Verilen: |AB| = 5, |BC| = 7      (figure.perpendicular = [])
Adım 1:  m(B) = 90°              rule: verilen        ← HATA
Adım 2:  |AC| = √74              rule: pisagor
```
`figure.perpendicular` boştur; diklik verilmemiştir, yalnızca öyle çizilmiştir.

**Karşı örnek (H1 DEĞİLDİR)**
Diklik `figure.perpendicular` içinde varsa ve öğrenci onu kullanıyorsa, bu doğru
bir adımdır. H1 için özniteliğin **gerçekten yok** olması gerekir.

**Not** — Bu sınıfın örneklerinin yarısı `bias: "misleading"`, yarısı
`bias: "neutral"` çizimle üretilir. Bu dengeleme, çizim biçiminin etkisini
ayrıştırılabilir kılar (K4 kolu).

---

### H2 — Tanım Karıştırma

Yükseklik, kenarortay ve açıortay kavramlarının birbiri yerine kullanılması.

**Tespit kuralı**
Adımda kullanılan teoremin gerektirdiği kenar tipi (`altitude` / `median` / `bisector`)
ile `figure` bloğundaki `segment.type` uyuşmuyorsa → H2.

**Tipik biçimler**
- Yüksekliği kenarortay sanıp `|BH| = |HC|` yazma *(P5 — kanonik)*
- Kenarortayı yükseklik sanıp dik açı varsayma *(P5)*
- Açıortayı kenarortay sanıp kenarı ikiye böldüğünü varsayma *(P5)*
- Benzer üçgenlerde karşılıklı kenarları yanlış eşleştirme *(P6)*

**Örnek**
```
Verilen: AH yüksekliktir          (segments: {A→H, type: "altitude"})
Adım 1:  |BH| = |HC|              rule: kenarortay     ← HATA
```
`kenarortay` teoremi `type == "median"` gerektirir; AH ise `altitude`.

**Karşı örnek (H2 DEĞİLDİR)**
Üçgen ikizkenar ise yükseklik ayağı ile orta nokta çakışır ve `|BH| = |HC|` doğrudur.
Ancak bu sonuca **kenarortay teoremiyle** değil, ikizkenarlık üzerinden varılmalıdır.
Öğrenci doğru gerekçeyi kullanıyorsa hata yoktur.

---

### H3 — Teoremi Ön Koşulsuz Uygulama

Teorem doğru bilinir, ancak uygulanabilme koşulları sağlanmadan kullanılır.

**Tespit kuralı**
Teorem kütüphanesindeki kuralın `preconditions` listesi, adımın bağlı olduğu
iddialarla karşılaştırılır; sağlanmayan koşul varsa → H3.

**H1'den farkı**
H1'de öğrenci eksik bilgiyi **çizimden okuyup "verilen" gibi kullanır**.
H3'te öğrenci koşulu **hiç denetlemeden** teoremi doğrudan uygular.
Ayrım, bir "verilen" iddiasının varlığındadır (bkz. §4.2).

**Tipik biçimler**
- Pisagor'u dik olmayan üçgende kullanma *(P3)*
- İkizkenar taban açıları özelliğini çeşitkenar üçgene uygulama *(P2)*
- Dış açı teoremini yanlış açı çiftine uygulama *(P1)*
- Üçgen eşitsizliğini denetlemeden uzunluk kabul etme *(P4)*
- Benzerlik oranını eşlik gibi kullanma *(P6)*

**Örnek**
```
Verilen: |AB| = 6, |AC| = 8, |BC| = 9
Adım 1:  m(B) = m(C)              rule: ikizkenar_taban   ← HATA
```
`ikizkenar_taban` teoremi iki kenarın eş olmasını gerektirir; 6 ≠ 8.

**Kapsam notu**
KKA'nın (iki kenar ve aralarında olmayan açı) eşlik kriteri sanılması bu sınıfın
en bilinen örneğidir, ancak **ispat tipi** bir konu olduğu için Faz 1 kapsamı dışındadır.

---

## 3. Kapsam dışı: aritmetik hata

Bir hesap hatası (örn. `180 − 65 − 40 = 65`) **akıl yürütme hatası değildir**:
çıkarım zinciri doğrudur, yalnızca aritmetik yanlıştır.

- Bir hata **sınıfı olarak sayılmaz**.
- Doğrulayıcı bunu yine de tespit eder ve **ayrı bir bayrak** olarak raporlar
  (`arithmetic_flag: true`), `error_class` alanına yazmaz.
- Üreteç aritmetik hata **enjekte etmez**.

---

## 4. Etiketleme kılavuzu

### 4.1 Tek hata kuralı

Her çözümde **tek bir hata** bulunur ve **tek bir adıma** atanır.

- Bir adım geçersizse ona bağlı sonraki adımlar da *kirlenmiştir*; bunlar ayrıca
  hata sayılmaz.
- Etiketlenecek adım, topolojik sırada **ilk geçersiz** adımdır.
- Üreteç de tek hata enjekte eder; iki kural birbiriyle tutarlıdır.

### 4.2 H1 mi H3 mü? — karar kuralı

En sık karışan iki sınıf. Ayrım şu soruyla yapılır:

> **Öğrenci eksik koşulu ayrı bir adımda "verilen" olarak iddia etmiş mi?**

| Durum | Sınıf |
|---|---|
| Evet — `rule: "verilen"` diyerek eksik özniteliği iddia etmiş | **H1** |
| Hayır — koşulu hiç anmadan teoremi doğrudan uygulamış | **H3** |

Örnek ayrımı:
```
H1:  Adım 1: m(B) = 90°   rule: verilen     ← eksik bilgi iddia edildi
     Adım 2: |AC| = √74   rule: pisagor

H3:  Adım 1: |AC| = √74   rule: pisagor     ← koşul hiç anılmadı
```

### 4.3 H2 mi H3 mü? — karar kuralı

| Durum | Sınıf |
|---|---|
| Kenar **tipi** yanlış eşleştirilmiş (`altitude` ↔ `median` ↔ `bisector`) | **H2** |
| Tip doğru, ama teoremin **başka** bir ön koşulu sağlanmıyor | **H3** |

### 4.4 Belirsiz durumlar

- **İki sınıf da uyuyorsa:** §4.2 ve §4.3'teki karar kurallarını sırayla uygula.
  Yine belirsizse H1 > H2 > H3 önceliğiyle etiketle ve vakayı
  `eval/agreement.md` içine kaydet.
- **Birden fazla adım hatalıysa:** topolojik sırada ilk olanı etiketle (§4.1).
- **Hata çizim kaynaklıysa ama öznitelik `figure`'da varsa:** hata yoktur (H0).

### 4.5 Çift etiketleme protokolü (yalnızca `data/handwritten/`)

Sentetik örneklerde etiket üreteçten gelir; kodlayıcı uyumu ölçülmez.
Elle yazılan 30 örnek için:

1. Çözümü yazan kişi **etiket koymaz**.
2. Birincil kodlayıcı (A1) 30 örneğin tamamını etiketler.
3. İkincil kodlayıcı (A2) aynı 30 örneği, A1'in etiketlerini **görmeden** etiketler.
4. Cohen kappa hesaplanır, uyuşmazlıklar `eval/agreement.md` içine yazılır.
5. Kılavuz netleştirilir, derlem dondurulur.

κ > 0.75 iyi kabul edilir. Düşük çıkarsa bu bir başarısızlık değil, **taksonominin
netleştirilmesi gerektiğinin sinyalidir** ve o hâliyle raporlanır.

---

## 5. Problem aileleri

Her hata sınıfı **en az iki farklı aileden** beslenir. Bu bir zorunluluktur:
tek aileye bağlı bir hata sınıfı olsaydı, model problem tipini tanıyarak hata
sınıfını bilebilir, sınıf ile aile arasında yapay bir korelasyon oluşurdu.

| Şablon | Aile | Teoremler | Beslediği sınıflar | Kazanım |
|---|---|---|---|---|
| P1-T01 | Üçgende dış açı | `ic_acilar_toplami`, `dis_aci` | H1, H3 | `MAT.9.3.1` |
| P2-T01 | İkizkenarda taban açıları | `ikizkenar_taban`, `ic_acilar_toplami` | **H1**, H3 | `MAT.9.3.1` |
| P3-T01 | Dik üçgende Pisagor | `pisagor` | **H1**, H3 | `MAT.9.4.4` |
| P3-T02 | Hipotenüse ait kenarortay | `hipotenus_kenarortay` | **H2**, H3 | `MAT.10.1.2` ⚠ |
| P4-T01 | Üçgen eşitsizliği | `ucgen_esitsizligi` | H1, H3 | `MAT.9.3.1` |
| P5-T01 | Yükseklik / kenarortay | `yukseklik`, `kenarortay` | **H2**, H1 | `MAT.10.1.2` ⚠ |
| P5-T02 | Açıortay / kenarortay | `aciortay`, `kenarortay` | **H2**, H3 | `MAT.10.1.2` ⚠ |
| P6-T01 | Benzerlik oranı | `benzerlik_orani` | H2, H3 | `MAT.9.4.2` |

Gerçekleşen dağılım: **H1 → 5 aile, H2 → 3 aile (P3, P5, P6), H3 → 6 aile.**

### Müfredat kaynağı ve sürüm uyarısı

Kodlar **Türkiye Yüzyılı Maarif Modeli** öğretim programından alınmıştır
(tymm.meb.gov.tr). 2018 programındaki `9.4.x` kodları **geçersizdir**: Maarif
Modeli 2025-2026'dan itibaren 9. sınıfta uygulanmaktadır ve 2026-2027'de de
yürürlüktedir.

İlgili öğrenme çıktıları:

| Kod | Metin | Sınıf |
|---|---|---|
| `MAT.9.3.1` | Üçgende açı ve kenarla ilgili özellikleri, üçgenin açıları ve kenarları arasındaki ilişkileri doğrulayabilme veya ispatlayabilme | 9 |
| `MAT.9.4.2` | İki üçgenin eş veya benzer olması için gerekli olan asgari koşullarla ilgili çıkarım yapabilme | 9 |
| `MAT.9.4.4` | Tales, Öklid ve Pisagor teoremlerini ispatlayabilme | 9 |
| `MAT.10.1.2` | Üçgenin yardımcı elemanlarının özellikleri ile ilgili çıkarım yapabilme | **10** |

### Kapsam kararı: 9–10. sınıf

Maarif Modeli'nde *üçgenin yardımcı elemanları* (yükseklik, kenarortay, açıortay)
9. sınıfta **yer almamaktadır**; 10. sınıfa (`MAT.10.1.2`) taşınmıştır. H2
sınıfının üç kaynağından ikisi (P3-T02, P5) bu çıktıya bağlıdır.

**Karar: hizalama "9–10. sınıf üçgenler" olarak genişletilmiştir.**

Gerekçe: yalnızca 9. sınıfta kalmak H2'yi tek kaynağa (P6) indirir ve sınıf ile
problem ailesi arasında yapay korelasyon doğurur (§5 giriş). Bu, üç hata sınıfını
dengeli biçimde ölçme olanağını ortadan kaldırır. Kapsamı bir sınıf genişletmenin
maliyeti yalnızca ifade değişikliğidir; yardımcı elemanlar zaten üçgen
geometrisinin ayrılmaz parçasıdır ve lise öğretim programının bütününde yer alır.

Bildiride kullanılacak ifade: **"MEB Türkiye Yüzyılı Maarif Modeli 9 ve 10. sınıf
matematik öğretim programı üçgenler kazanımları ile hizalanmıştır."**
"9. sınıf ile hizalıdır" denmeyecektir.

> Kodlar tymm.meb.gov.tr üzerinden alınmıştır; bildiriye girmeden önce öğretim
> programının resmî PDF'inden ayrıca teyit edilmelidir.

---

## 6. Sınıf dağılımı hedefi

| Sınıf | Sentetik | Elle yazılmış | Toplam |
|---|---|---|---|
| H0 | 100 | 8 | 108 |
| H1 | 100 | 8 | 108 |
| H2 | 100 | 7 | 107 |
| H3 | 100 | 7 | 107 |
| **Toplam** | **400** | **30** | **430** |

Elle yazılan küme sentetik kümeye **karıştırılmaz**; ayrı tutulmuş gerçekçilik
denetimi ve κ ölçümü kümesidir. Sonuçlar iki küme için **ayrı ayrı** raporlanır.

---

## 7. Üretece giren kısıtlar

Şablon izini önlemek için üreteç aşağıdakileri zorunlu olarak uygular:

- Köşe adları değişir (ABC, KLM, DEF, PQR, …)
- Sayısal değerler rastgeleleşir, geometrik tutarlılık korunur
- **Hatalı adımın konumu dolaştırılır** — hep 1. adımda olamaz
- Adım sayısı 2–5 arasında değişir; doğru ama sonuca katkısız dolgu adımları eklenir
- 2–3 farklı ifade şablonu kullanılır
- H1 örneklerinin yarısı `misleading`, yarısı `neutral` çizimle üretilir
- Her hata sınıfı en az iki problem ailesine dağıtılır

> Hatalı adımın konumu dolaştırılmazsa, model "ilk adımı söyle" diyerek yüksek
> yerelleştirme skoru alır ve M3 metriği anlamsızlaşır.
