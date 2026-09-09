# Elle Yazılan Küme (30 örnek)

Bu küme **sentetik derleme karıştırılmaz**. Ayrı tutulmuş bir değerlendirme
kümesidir ve iki ayrı işi görür:

1. **Gerçekçilik denetimi** — dil modeli hem sentetik hem bu küme üzerinde ölçülür.
   Skorlar yakınsa sentetik verinin temsil gücü savunulabilir; ayrışıyorsa bu da
   raporlanacak bir bulgudur. *"Veriniz yapay"* eleştirisine verilecek en güçlü cevap budur.
2. **Cohen kappa** — sentetik veride etiket üreteçten geldiği için kodlayıcı uyumu
   diye bir şey yoktur. Bu kümede iki bağımsız kişi etiketler ve κ hesaplanır;
   taksonominin öznel olmadığının kanıtı budur.

> **Bu örnekleri üreteç yazmaz ve yazamaz.** Üreteci tasarlayan kişi bu örnekleri
> de yazarsa küme "üreteçten bağımsız" olmaktan çıkar, aynı kalıpların elle
> yazılmış hâline dönüşür. Kümenin tüm değeri bu bağımsızlıktan gelir.

---

## Klasör düzeni ve körlük

```
solutions/   → çözümler, ETİKETSİZ    (gönüllüler yazar)
labels/      → etiketler, ayrı dosyalarda (kodlayıcılar doldurur)
   A1.json      birincil kodlayıcı
   A2.json      ikincil kodlayıcı — A1'i GÖRMEDEN doldurur
```

Çözüm dosyalarında `label` alanı **yoktur**; şema bunu reddeder. Etiketler ayrı
tutulduğu için ikinci kodlayıcı birincinin kararını teknik olarak göremez.
Körlük bir söz değil, dosya düzeninin sonucudur.

---

## Protokol (docs/taksonomi.md §4.5)

| Adım | Kim | Ne yapar |
|---|---|---|
| 1. Üretim | Gönüllüler (2–3 kişi) | Çözüm adımlarını yazar. Bir kısmı kasıtlı hatalı, bir kısmı doğru. **Etiket koymaz.** |
| 2. Birincil etiketleme | Araştırmacı (A1) | 30 örneğin tamamını etiketler → `labels/A1.json` |
| 3. İkincil etiketleme | Bağımsız kodlayıcı (A2) | Aynı 30 örneği A1'i görmeden etiketler → `labels/A2.json` |
| 4. Uyum ölçümü | Araştırmacı | `python eval/agreement.py` → κ ve uyuşmazlık listesi |
| 5. Dondurma | Araştırmacı | Kılavuz netleştirilir, küme değişmez kabul edilir |

κ > 0.75 iyi kabul edilir. Düşük çıkarsa bu bir başarısızlık **değil**,
taksonominin netleştirilmesi gerektiğinin sinyalidir ve o hâliyle raporlanır.

### Gönüllülere verilecek yönerge

> Sana bir üçgen problemi ve çözüm adımlarının yazılacağı bir form verilecek.
> Bazı çözümleri **doğru**, bazılarını **kasıtlı hatalı** yaz. Hatayı yaparken
> gerçek bir öğrencinin düşebileceği türden bir hata yapmaya çalış: şekle bakıp
> verilmemiş bir şeyi varsaymak, kavramları karıştırmak, bir kuralı koşulu
> sağlanmadan uygulamak gibi.
>
> **Hangi hatayı yaptığını yazma.** Etiketlemeyi başkası yapacak.

Hata sınıflarının tanımlarını gönüllülere **verme** — verirsen sınıfa göre örnek
üretmeye başlarlar ve küme sentetik derlemin bir kopyasına dönüşür.

---

## Gönüllülere problem föyü

Gönüllünün en çok takıldığı yer "hangi problemi yazayım?" sorusudur. Föy bunu
çözer — 30 problem, altı aileye dengeli dağılmış, yazdırılabilir:

```bash
python src/worksheet.py -n 30
```

`data/handwritten/foy.html` oluşur; tarayıcıda açıp yazdırabilirsin. Her problem
soruyu, şekli ve verilenler listesini içerir; altında çözümün yazılacağı boş
satırlar vardır.

Föy **hata sınıflarını, çözüm adımlarını ve hangi hatanın beklendiğini
içermez**. Gönüllü problemi görür, çözümü kendi yazar, hata yapıp yapmayacağına
kendi karar verir. Sınıf dağılımı böylece kendiliğinden oluşur.

Verilenleri eksik olan problemler bilinçli olarak **yanıltıcı çizimle** gelir:
çözülemeyen bir soruyu nötr çizimle vermek gönüllüye kusurlu soru vermek olurdu.
Ders kitabının bu durumda yaptığı da şekli tuzaklı çizmektir.

---

## Bir örnek nasıl yazılır

**Önerilen yol — form arayüzü.** JSON düzenlemeye gerek yok:

```bash
streamlit run app.py
```

Sol menüden **Örnek yaz** sayfasını aç. Form şekli canlı çizer, eksikleri
anında bildirir ve kaydederken koordinatları kendisi hesaplar.

Etiketleme için aynı uygulamadaki **Etiketle** sayfasını kullan. Sayfa, seçili
kodlayıcı dışındaki etiketleri ve doğrulayıcının teşhisini **göstermez** —
körlük arayüz düzeyinde de korunur.

Alternatif — boş dosya oluşturup elle doldurmak:

```bash
python src/handwritten.py --new EL-0001
```

`ORNEK-FORMAT.json` dosyası biçimi gösterir; **kümenin parçası değildir** ve
yükleyici tarafından atlanır.

Doldurulacak alanlar:

| Alan | Açıklama |
|---|---|
| `soru` | Problemin Türkçe metni |
| `figure` | **Yalnızca verilenler.** Burada olmayan hiçbir şey "verilmiş" sayılmaz. |
| `steps` | Çözüm adımları: iddia + kullanılan kural + `refs` |
| `rendering.bias` | `misleading` (çizim tuzak kurar) veya `neutral` |

`rendering.coords` **elle doldurulmaz** — çizim motoru hesaplar:

```bash
python src/handwritten.py --render
```

Denetim:

```bash
python src/handwritten.py --check
```

Şema uyumu, adım bağımlılıkları ve `refs` eksikliklerini raporlar.

---

## Hedef dağılım

| Sınıf | Adet |
|---|---|
| H0 — hatasız | 8 |
| H1 — şekle aşırı güvenme | 8 |
| H2 — tanım karıştırma | 7 |
| H3 — ön koşulsuz teorem | 7 |
| **Toplam** | **30** |

Bu dağılım **hedeftir, kota değildir**. Gönüllüler sınıfları bilmeden yazdığı
için gerçekleşen dağılım farklı çıkabilir; etiketleme sonrası ne çıktıysa o
raporlanır. Dağılımı tutturmak için etiket değiştirilmez.

---

## Etik

Bu küme **gerçek öğrenci verisi değildir**. Gönüllüler öğrenci değil, öğrenci
hatası taklidi üreten yetişkinlerdir. Bu bir sınırlılıktır ve bildiride açıkça
beyan edilir. Gerçek öğrenci verisiyle çalışma, KVKK aydınlatma metni, veli
onamı ve etik kurul izniyle ayrı bir faz olarak ele alınacaktır.
