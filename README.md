# AI Gateway — مفتاح واحد ⇦ عشرات النماذج

بوابة متوافقة مع **OpenAI API** تجمع **عدة مفاتيح API خلف مفتاح واحد**، وتوزّع الطلبات
عليها بالتناوب (round-robin) مع **تبديل تلقائي (failover)** عند الحد/النفاد (429/402/5xx).
النتيجة: رصيد إجمالي أكبر بكثير، موثوقية أعلى، وعشرات النماذج (GPT / Claude / Gemini /
النماذج المفتوحة …) عبر نقطة واحدة موحّدة.

> ⚠️ استخدم **مفاتيحك الخاصة** التي تملكها بشكل شرعي، والتزم بشروط كل مزوّد.
> هذا المشروع للاستخدام المشروع (تجميع مفاتيحك + موازنة الحِمل)، وليس للتحايل على الحدود.

## التشغيل

```bash
cd backend
pip install -r requirements.txt
cp keys.example.json keys.json      # ثم عدّل المزوّدين والمفاتيح والنماذج
cp .env.example .env                # اختياري: لضبط مفتاح البوابة
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

ثم افتح `web/index.html` في المتصفح، ضع العنوان `http://localhost:8080`، واضغط
"اتصال وتحميل النماذج".

## الاستخدام كـ OpenAI API عادي

```python
from openai import OpenAI
client = OpenAI(base_url="http://localhost:8080/v1", api_key="my-secret-gateway-key")
r = client.chat.completions.create(
    model="openai/gpt-5.6",
    messages=[{"role": "user", "content": "مرحبا"}],
)
print(r.choices[0].message.content)
```

## نقاط النهاية
| المسار | الوصف |
|---|---|
| `GET /v1/models` | كل النماذج المتاحة عبر كل المزوّدين |
| `POST /v1/chat/completions` | متوافق مع OpenAI (يدعم `stream`) |
| `GET /admin/stats` | استخدام كل مفتاح + الأخطاء + التبريد |
| `GET /admin/no-limit` | حالة ميزة no-limit (المزوّدون المكتشفون + عدد المفاتيح) |

## كيف يعمل التدوير
1. كل نموذج مربوط بمزوّد. كل مزوّد لديه **مجمّع مفاتيح**.
2. عند كل طلب يُختار المفتاح التالي دورياً.
3. إذا رجع 401/402/403/429/5xx → يُوضع المفتاح في تبريد 60 ثانية ويُجرّب التالي.
4. لا يفشل الطلب إلا إذا فشلت **كل** المفاتيح.

## ميزة No-Limit (لا حدود)
تتيح لك إضافة **حسابات/مفاتيح متعددة** لنفس المزوّد من `pi` أو أي مزوّد آخر، بحيث يتنقل الـ Gateway بينها تلقائياً عند نفاد الرصيد أو Rate Limit.

### كيف تعمل
1. الـ Gateway **يكتشف تلقائياً** المزوّدين المضافين في `~/.pi/agent/models.json`
2. أضِف مفاتيحك الإضافية في ملف `backend/keys_no_limit.json`
3. المفاتيح الإضافية **تُضاف** إلى المفاتيح الموجودة (لا تستبدلها)
4. عند فشل أي مفتاح (401/402/429/5xx) → يُحجب 60 ثانية ويُجرّب المفتاح التالي

### التفعيل
```bash
cd backend
# يُنشئ الملف التلقائياً مع أول تشغيل؛ عدّله بمفاتيحك الحقيقية
nano keys_no_limit.json
```

مثال:
```json
{
  "Alibaba": [
    "sk-real-alibaba-account-1",
    "sk-real-alibaba-account-2",
    "sk-real-alibaba-account-3"
  ],
  "NVIDIA": [
    "nvapi-real-nvidia-account-1",
    "nvapi-real-nvidia-account-2"
  ]
}
```

### التحقق من الدمج
```bash
curl http://localhost:8080/admin/no-limit
curl http://localhost:8080/admin/stats
```

## المزوّدون المدعومون
أي مزوّد **متوافق مع OpenAI** (OpenRouter, Groq, Together, DeepSeek, Z.ai/GLM,
OpenAI, xAI …). أضِفه ببساطة في `keys.json` بعنوانه ومفاتيحه ونماذجه.
> OpenRouter وحده يمنحك عشرات النماذج (GPT/Claude/Gemini/GLM…) عبر واجهة واحدة.

## البنية
```
ai_gateway/
├─ backend/   FastAPI gateway (main.py, requirements.txt, keys.example.json, .env.example)
└─ web/       لوحة تحكم (index.html, styles.css, app.js)
```
