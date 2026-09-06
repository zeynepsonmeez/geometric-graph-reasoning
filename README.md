# geometric-graph-reasoning

**Görsel Geometrik Yapıların Graf Tabanlı Temsili ile Öğrenci Matematiksel Akıl
Yürütme Hatalarının Yapay Zekâ Destekli Tespiti**

Üçgen geometrisinde öğrenci çözümlerini iki ayrı graf olarak modelleyip, hatayı
bu grafların üzerinde **adım düzeyinde konumlandıran** bir sistem.

Çıktı "yanlış" değil, şu biçimdedir:

> *3. adımda, şekilde dik görünen açıyı verilmiş kabul ettin.*

---

## Neden graf?

Geometrik bir çözüm iki ayrı ilişki ağı içerir ve ikisi de düz metin temsilinde kaybolur:

| Graf | İçerik |
|---|---|
| **Şekil grafı** (G₀) | Hangi nokta hangi doğru üzerinde, hangi kenar hangi açının karşısında, ne verilmiş |
| **Akıl yürütme grafı** (G₁) | Hangi ara sonuç, hangi verilenden, hangi teoremle türetildi (DAG) |

Sistemin merkezî fikri bu ikisi **arasındaki tutarsızlığı** aramaktır:

> Akıl yürütme grafındaki bir kenar, şekil grafında **bulunmayan** bir özniteliğe
> dayanıyorsa → öğrenci çizimden geçersiz bilgi çıkarmıştır.

Bu, yaygın bir pedagojik gözlemi hesaplanabilir bir koşula çevirir.

---

## Hata sınıfları

| Sınıf | Ad | Tespit kuralı |
|---|---|---|
| **H0** | Hatasız | Tüm adımların ön koşulları sağlanıyor |
| **H1** | Şekle aşırı güvenme | Adımın dayandığı öznitelik `figure` bloğunda yok |
| **H2** | Tanım karıştırma | Yükseklik / kenarortay / açıortay tipi uyuşmuyor |
| **H3** | Ön koşulsuz teorem | Teoremin `preconditions` listesi sağlanmıyor |

Tanımlar, karar kuralları ve örnekler: [`docs/taksonomi.md`](docs/taksonomi.md)

Aritmetik hatalar bilinçli olarak kapsam dışıdır — bunlar akıl yürütme hatası
değildir, ayrı bir bayrak olarak raporlanır.

---

## Çizim neden bilerek yanıltıcı?

Ders kitabı şekilleri ölçekli değildir: kenara "7" yazılır ama 7 birim çizilmez.
H1 sınıfı tam olarak bu olgu yüzünden vardır. Şekil ölçekli çizilirse çizim hiç
yanıltmaz ve sınıf anlamsızlaşır.

Çizim motoru bu davranışı taklit eder:

| Nitelik | Davranış |
|---|---|
| Topoloji | Birebir doğru |
| Verilen nitel ilişkiler (diklik, eşlik) | Birebir doğru, işaretli |
| Metrik değerler | **Ölçekli değil, etiketli** |
| Verilmemiş nitelikler | **Serbest** — `rendering.bias` belirler |

`bias: "misleading"` verilmemiş nicelikleri özel durum *gibi görünecek* şekilde
seçer; `bias: "neutral"` belirgin biçimde genel görünür.

---

## Yöntem

| Bileşen | Rol |
|---|---|
| Sembolik doğrulayıcı | **Etiketleme oracle'ı ve ürünün motoru.** Ölçüm nesnesi değildir. |
| Dil modeli | **Ölçülen tek şey.** Ne üreteci ne doğrulayıcıyı görür. |

**Araştırma sorusu:** Bir dil modeli, geometrik bir akıl yürütme zincirindeki
hatayı, sembolik bir doğrulayıcı kadar isabetli biçimde *yerelleştirebilir* mi?

Deney kolları: `K1` grafsız · `K2` şekil grafı verilmiş · `K3` few-shot ·
`K4` çizim görseli (isteğe bağlı).

Metrikler, **rastgele taban çizgisiyle birlikte** raporlanır:

| | Soru | Rastgele taban |
|---|---|---|
| M1 | Hata var mı? | ~0.50 |
| M2 | Hangi tür? | ~0.25 |
| M3 | **Hangi adımda?** | **~1/n** |

Çözümler 2–5 adımlı olduğu için M3'te rastgele tahmin %25–50 alır; taban çizgisi
olmadan bu metrik yorumlanamaz.

---

## Mimari kuralı

> `src/generator.py` ile `src/verifier.py` **birbirinden hiçbir modül import etmez.**

Üreteç hataları kurar, doğrulayıcı geçerliliği denetler. Aynı kodu paylaşırlarsa
doğrulayıcı tanım gereği %100 doğruluk alır — bu bir sonuç değil, tanımın tekrarıdır.
Ortak olan spesifikasyondur (`docs/taksonomi.md`), kod değildir.

Bu kural [`tests/test_independence.py`](tests/test_independence.py) ile denetlenir.
Aynı test, doğrulayıcının `rendering` bloğunu okumadığını da doğrular.

---

## Kapsam

**İçinde:** üçgen · hesaplama tipi sorular · 9. sınıf üçgenler ünitesi ·
yapılandırılmış adım girişi · 3 hata sınıfı + hatasız

**Dışında (ileri faz):** çember/çokgen · ispat tipi sorular · el yazısı tanıma ·
gerçek öğrenci verisi (KVKK + etik kurul) · GNN

---

## Veri

| Küme | Sayı | Amaç |
|---|---|---|
| `data/synthetic/` | 400 | Üreteçten, dengeli dağılım |
| `data/handwritten/` | 30 | **Ayrı tutulur.** Gerçekçilik denetimi + Cohen κ |

Bu fazda **hiçbir gerçek öğrenci verisi toplanmaz, işlenmez veya saklanmaz.**

---

## Dizin yapısı

```
docs/taksonomi.md          H0–H3 tanımları, karar kuralları — ORTAK SPESİFİKASYON
schema/                    JSON şeması (figure / rendering / steps / label)
src/theorems.py            9 teorem + ön koşulları
src/generator.py           sentetik üreteç
src/renderer.py            çizim motoru + bias
src/verifier.py            sembolik doğrulayıcı
src/llm_checker.py         K1–K4 kolları
eval/                      deney, taban çizgileri, kappa raporu
```

---

## Kurulum

```bash
pip install -r requirements.txt
```

Dil modeli kolu için `.env` içine API anahtarı konur (`.gitignore`'dadır).

---

## Durum

Faz 0 / Gün 1–2 — taksonomi, şema ve teorem kütüphanesi kuruldu.
Üreteç, çizim motoru ve doğrulayıcı henüz yazılmadı.
