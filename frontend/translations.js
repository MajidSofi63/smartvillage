// translations.js
// Holds the English/Hindi/Urdu text for every static label in the UI.
// Only the UI "chrome" (labels, headings, buttons) is translated here - results
// coming back from the backend (advice, scheme names, etc.) stay in English for
// now, since translating those live would need another API call to Gemini.

const translations = {

  en: {
    appTitle: "🌾 AI Smart Village Platform",
    navDashboard: "Dashboard", navCrop: "Crop Prediction", navTele: "Telemedicine",
    navSchemes: "Govt. Schemes", navWater: "Water Management", navDisaster: "Disaster Alerts",
    navEmployment: "Employment", navAssistant: "Assistant", navAdmin: "Admin",

    adminHeading: "Admin Panel", adminDesc: "Full visibility into everyone using the platform.",
    labelAdminPassword: "Admin Password",
    adminWorkersTitle: "Registered Workers", adminEmployersTitle: "Registered Employers",
    adminJobsTitle: "All Job Postings", adminApplicationsTitle: "All Applications",

    dashHeading: "Welcome",
    dashIntro: "A single platform that brings together crop prediction, telemedicine, government scheme discovery, water management, disaster alerts, and employment matching for rural communities.",
    cardCropTitle: "🌱 Crop Prediction", cardCropDesc: "Estimate crop yield from rainfall, pesticide use, and temperature.",
    cardTeleTitle: "🩺 Telemedicine", cardTeleDesc: "Describe your symptoms and get first-aid guidance.",
    cardSchemesTitle: "🏛️ Govt. Schemes", cardSchemesDesc: "Find welfare schemes you're eligible for.",
    cardWaterTitle: "💧 Water Management", cardWaterDesc: "Check soil moisture and reservoir levels.",
    cardDisasterTitle: "⛈️ Disaster Alerts", cardDisasterDesc: "Live weather-based warnings for your area.",
    cardEmploymentTitle: "💼 Employment", cardEmploymentDesc: "Find local jobs that match your skills.",

    cropHeading: "Crop Yield Prediction",
    cropDesc: "Predicts upcoming yield based on current conditions (not past years).",
    labelArea: "Country/Area (type to search)", labelCrop: "Crop", labelRainfall: "Average Rainfall (mm/year)",
    labelPesticides: "Pesticides Used (tonnes)", labelTemperature: "Average Temperature (°C)",
    btnPredict: "Predict Yield",

    teleHeading: "Telemedicine Assistant",
    teleDesc: "Describe your symptoms in plain words (e.g. \"chest pain\", \"leg pain\", \"fever\").",
    teleDisclaimer: "⚠️ This tool does NOT diagnose you. It only gives general guidance - always see a doctor.",
    labelSymptoms: "Your Symptoms", btnCheckSymptoms: "Check Symptoms",

    schemesHeading: "Government Scheme Finder",
    schemesDesc: "Enter your details to see which welfare schemes you qualify for.",
    labelAge: "Your Age", labelIncome: "Annual Household Income (₹)",
    labelLand: "Do you own agricultural land?", labelCategory: "Category",
    optYes: "Yes", optNo: "No", btnFindSchemes: "Find Eligible Schemes",

    waterHeading: "Smart Water Management",
    waterDesc: "Real soil moisture and rainfall data for your area, via Open-Meteo.",
    btnWaterRefresh: "Check Water Status",

    disasterHeading: "Disaster Alert System",
    disasterDesc: "Live weather, forecast, and air quality via OpenWeather, checked against disaster risk rules.",
    labelCity: "Your City/Town", btnCheckWeather: "Check Weather Alerts",

    employmentHeading: "Employment Matching",
    employmentDesc: "A real job board: log in as a worker or an employer.",
    iAmWorker: "I'm Looking for Work", iAmEmployer: "I'm Hiring",
    iAmWorkerDesc: "Register your skills and apply to local jobs",
    iAmEmployerDesc: "Post an opening and find local workers",
    btnLogin: "Login", btnRegister: "Register", labelPassword: "Password", btnBack: "← Back",
    welcomeText: "Welcome,", btnLogout: "Logout",
    labelName: "Your Name", labelEmail: "Email", labelPhone: "Phone Number", labelLocation: "Location",
    btnDelete: "Delete", btnWithdraw: "Withdraw",
    labelSkills: "Your Skills",
    availableJobsTitle: "Available Jobs", myApplicationsTitle: "My Applications",
    labelJobTitle: "Job Title", labelRequiredSkills: "Required Skills",
    labelJobType: "Type", labelContact: "Contact Info",
    postJobTitle: "Post a New Job", btnPostJob: "Post Job", myJobsTitle: "My Posted Jobs",

    assistantHeading: "Ask the Assistant",
    assistantDesc: "Ask anything about the platform in plain language - it will guide you to the right tool.",
    assistantPlaceholder: "e.g. How do I check if I'm eligible for a scheme?",
    btnSend: "Send",
  },

  hi: {
    appTitle: "🌾 एआई स्मार्ट विलेज प्लेटफॉर्म",
    navDashboard: "डैशबोर्ड", navCrop: "फसल भविष्यवाणी", navTele: "टेलीमेडिसिन",
    navSchemes: "सरकारी योजनाएं", navWater: "जल प्रबंधन", navDisaster: "आपदा चेतावनी",
    navEmployment: "रोजगार", navAssistant: "सहायक", navAdmin: "एडमिन",

    adminHeading: "एडमिन पैनल", adminDesc: "प्लेटफॉर्म का उपयोग करने वाले सभी लोगों की पूरी जानकारी।",
    labelAdminPassword: "एडमिन पासवर्ड",
    adminWorkersTitle: "पंजीकृत कर्मचारी", adminEmployersTitle: "पंजीकृत नियोक्ता",
    adminJobsTitle: "सभी नौकरी पोस्टिंग", adminApplicationsTitle: "सभी आवेदन",

    dashHeading: "स्वागत है",
    dashIntro: "एक ही मंच जो ग्रामीण समुदायों के लिए फसल भविष्यवाणी, टेलीमेडिसिन, सरकारी योजना खोज, जल प्रबंधन, आपदा चेतावनी और रोजगार मिलान को एक साथ लाता है।",
    cardCropTitle: "🌱 फसल भविष्यवाणी", cardCropDesc: "वर्षा, कीटनाशक उपयोग और तापमान से फसल की उपज का अनुमान लगाएं।",
    cardTeleTitle: "🩺 टेलीमेडिसिन", cardTeleDesc: "अपने लक्षण बताएं और प्राथमिक चिकित्सा मार्गदर्शन प्राप्त करें।",
    cardSchemesTitle: "🏛️ सरकारी योजनाएं", cardSchemesDesc: "उन कल्याणकारी योजनाओं को खोजें जिनके आप पात्र हैं।",
    cardWaterTitle: "💧 जल प्रबंधन", cardWaterDesc: "मिट्टी की नमी और जलाशय के स्तर की जांच करें।",
    cardDisasterTitle: "⛈️ आपदा चेतावनी", cardDisasterDesc: "आपके क्षेत्र के लिए लाइव मौसम आधारित चेतावनी।",
    cardEmploymentTitle: "💼 रोजगार", cardEmploymentDesc: "अपने कौशल से मेल खाने वाली स्थानीय नौकरियां खोजें।",

    cropHeading: "फसल उपज भविष्यवाणी",
    cropDesc: "वर्तमान परिस्थितियों के आधार पर आगामी उपज का अनुमान (पिछले वर्षों का नहीं)।",
    labelArea: "देश/क्षेत्र (खोजने के लिए टाइप करें)", labelCrop: "फसल", labelRainfall: "औसत वर्षा (मिमी/वर्ष)",
    labelPesticides: "उपयोग किए गए कीटनाशक (टन)", labelTemperature: "औसत तापमान (°C)",
    btnPredict: "उपज का अनुमान लगाएं",

    teleHeading: "टेलीमेडिसिन सहायक",
    teleDesc: "अपने लक्षण सरल शब्दों में बताएं (जैसे \"सीने में दर्द\", \"पैर में दर्द\", \"बुखार\")।",
    teleDisclaimer: "⚠️ यह उपकरण निदान नहीं करता। यह केवल सामान्य मार्गदर्शन देता है - हमेशा डॉक्टर से मिलें।",
    labelSymptoms: "आपके लक्षण", btnCheckSymptoms: "लक्षण जांचें",

    schemesHeading: "सरकारी योजना खोजक",
    schemesDesc: "यह जानने के लिए अपना विवरण दर्ज करें कि आप किन योजनाओं के लिए पात्र हैं।",
    labelAge: "आपकी उम्र", labelIncome: "वार्षिक पारिवारिक आय (₹)",
    labelLand: "क्या आपके पास कृषि भूमि है?", labelCategory: "श्रेणी",
    optYes: "हां", optNo: "नहीं", btnFindSchemes: "पात्र योजनाएं खोजें",

    waterHeading: "स्मार्ट जल प्रबंधन",
    waterDesc: "Open-Meteo के माध्यम से आपके क्षेत्र के लिए वास्तविक मिट्टी नमी और वर्षा डेटा।",
    btnWaterRefresh: "जल स्थिति जांचें",

    disasterHeading: "आपदा चेतावनी प्रणाली",
    disasterDesc: "OpenWeather के माध्यम से लाइव मौसम, पूर्वानुमान और वायु गुणवत्ता, आपदा जोखिम नियमों के विरुद्ध जांची गई।",
    labelCity: "आपका शहर/कस्बा", btnCheckWeather: "मौसम चेतावनी जांचें",

    employmentHeading: "रोजगार मिलान",
    employmentDesc: "एक वास्तविक जॉब बोर्ड: कर्मचारी या नियोक्ता के रूप में लॉगिन करें।",
    iAmWorker: "मुझे काम चाहिए", iAmEmployer: "मुझे भर्ती करनी है",
    iAmWorkerDesc: "अपने कौशल पंजीकृत करें और स्थानीय नौकरियों के लिए आवेदन करें",
    iAmEmployerDesc: "एक अवसर पोस्ट करें और स्थानीय कर्मचारी खोजें",
    btnLogin: "लॉगिन", btnRegister: "पंजीकरण करें", labelPassword: "पासवर्ड", btnBack: "← वापस",
    welcomeText: "स्वागत है,", btnLogout: "लॉगआउट",
    labelName: "आपका नाम", labelEmail: "ईमेल", labelPhone: "फ़ोन नंबर", labelLocation: "स्थान",
    btnDelete: "हटाएं", btnWithdraw: "वापस लें",
    labelSkills: "आपके कौशल",
    availableJobsTitle: "उपलब्ध नौकरियां", myApplicationsTitle: "मेरे आवेदन",
    labelJobTitle: "नौकरी का शीर्षक", labelRequiredSkills: "आवश्यक कौशल",
    labelJobType: "प्रकार", labelContact: "संपर्क जानकारी",
    postJobTitle: "नई नौकरी पोस्ट करें", btnPostJob: "नौकरी पोस्ट करें", myJobsTitle: "मेरी पोस्ट की गई नौकरियां",

    assistantHeading: "सहायक से पूछें",
    assistantDesc: "प्लेटफॉर्म के बारे में सरल भाषा में कुछ भी पूछें - यह आपको सही उपकरण तक मार्गदर्शन करेगा।",
    assistantPlaceholder: "जैसे मैं कैसे जांचूं कि मैं किसी योजना के लिए पात्र हूं?",
    btnSend: "भेजें",
  },

  ur: {
    appTitle: "🌾 اے آئی اسمارٹ ولیج پلیٹ فارم",
    navDashboard: "ڈیش بورڈ", navCrop: "فصل کی پیشگوئی", navTele: "ٹیلی میڈیسن",
    navSchemes: "سرکاری اسکیمیں", navWater: "پانی کا انتظام", navDisaster: "آفت کی وارننگ",
    navEmployment: "روزگار", navAssistant: "معاون", navAdmin: "ایڈمن",

    adminHeading: "ایڈمن پینل", adminDesc: "پلیٹ فارم استعمال کرنے والے سب کی مکمل معلومات۔",
    labelAdminPassword: "ایڈمن پاس ورڈ",
    adminWorkersTitle: "رجسٹرڈ کارکن", adminEmployersTitle: "رجسٹرڈ آجر",
    adminJobsTitle: "تمام نوکری کی پوسٹنگ", adminApplicationsTitle: "تمام درخواستیں",

    dashHeading: "خوش آمدید",
    dashIntro: "ایک ہی پلیٹ فارم جو دیہی برادریوں کے لیے فصل کی پیشگوئی، ٹیلی میڈیسن، سرکاری اسکیم کی تلاش، پانی کا انتظام، آفت کی وارننگ اور روزگار کی تلاش کو ایک ساتھ لاتا ہے۔",
    cardCropTitle: "🌱 فصل کی پیشگوئی", cardCropDesc: "بارش، کیڑے مار ادویات اور درجہ حرارت سے فصل کی پیداوار کا اندازہ لگائیں۔",
    cardTeleTitle: "🩺 ٹیلی میڈیسن", cardTeleDesc: "اپنی علامات بتائیں اور ابتدائی طبی رہنمائی حاصل کریں۔",
    cardSchemesTitle: "🏛️ سرکاری اسکیمیں", cardSchemesDesc: "وہ فلاحی اسکیمیں تلاش کریں جن کے آپ اہل ہیں۔",
    cardWaterTitle: "💧 پانی کا انتظام", cardWaterDesc: "مٹی کی نمی اور ذخائر کی سطح چیک کریں۔",
    cardDisasterTitle: "⛈️ آفت کی وارننگ", cardDisasterDesc: "آپ کے علاقے کے لیے لائیو موسمی وارننگز۔",
    cardEmploymentTitle: "💼 روزگار", cardEmploymentDesc: "اپنی مہارتوں سے میل کھاتی مقامی نوکریاں تلاش کریں۔",

    cropHeading: "فصل کی پیداوار کی پیشگوئی",
    cropDesc: "موجودہ حالات کی بنیاد پر آئندہ پیداوار کا اندازہ (ماضی کے سالوں کا نہیں)۔",
    labelArea: "ملک/علاقہ (تلاش کے لیے ٹائپ کریں)", labelCrop: "فصل", labelRainfall: "اوسط بارش (ملی میٹر/سال)",
    labelPesticides: "استعمال شدہ کیڑے مار ادویات (ٹن)", labelTemperature: "اوسط درجہ حرارت (°C)",
    btnPredict: "پیداوار کا اندازہ لگائیں",

    teleHeading: "ٹیلی میڈیسن معاون",
    teleDesc: "اپنی علامات آسان الفاظ میں بتائیں (مثلاً \"سینے میں درد\"، \"ٹانگ میں درد\"، \"بخار\")۔",
    teleDisclaimer: "⚠️ یہ ٹول تشخیص نہیں کرتا۔ یہ صرف عمومی رہنمائی دیتا ہے - ہمیشہ ڈاکٹر سے رجوع کریں۔",
    labelSymptoms: "آپ کی علامات", btnCheckSymptoms: "علامات چیک کریں",

    schemesHeading: "سرکاری اسکیم فائنڈر",
    schemesDesc: "یہ جاننے کے لیے اپنی تفصیلات درج کریں کہ آپ کن اسکیموں کے اہل ہیں۔",
    labelAge: "آپ کی عمر", labelIncome: "سالانہ گھریلو آمدنی (₹)",
    labelLand: "کیا آپ زرعی زمین کے مالک ہیں؟", labelCategory: "زمرہ",
    optYes: "ہاں", optNo: "نہیں", btnFindSchemes: "اہل اسکیمیں تلاش کریں",

    waterHeading: "اسمارٹ واٹر مینجمنٹ",
    waterDesc: "Open-Meteo کے ذریعے آپ کے علاقے کے لیے حقیقی مٹی کی نمی اور بارش کا ڈیٹا۔",
    btnWaterRefresh: "پانی کی صورتحال چیک کریں",

    disasterHeading: "آفت کی وارننگ کا نظام",
    disasterDesc: "OpenWeather کے ذریعے لائیو موسم، پیشگوئی اور ہوا کا معیار، آفت کے خطرے کے اصولوں کے خلاف جانچا گیا۔",
    labelCity: "آپ کا شہر/قصبہ", btnCheckWeather: "موسمی وارننگز چیک کریں",

    employmentHeading: "روزگار میچنگ",
    employmentDesc: "ایک حقیقی جاب بورڈ: کارکن یا آجر کے طور پر لاگ ان کریں۔",
    iAmWorker: "مجھے کام چاہیے", iAmEmployer: "مجھے بھرتی کرنی ہے",
    iAmWorkerDesc: "اپنی مہارتیں رجسٹر کریں اور مقامی نوکریوں کے لیے درخواست دیں",
    iAmEmployerDesc: "ایک آسامی پوسٹ کریں اور مقامی کارکن تلاش کریں",
    btnLogin: "لاگ ان", btnRegister: "رجسٹر کریں", labelPassword: "پاس ورڈ", btnBack: "← واپس",
    welcomeText: "خوش آمدید,", btnLogout: "لاگ آؤٹ",
    labelName: "آپ کا نام", labelEmail: "ای میل", labelPhone: "فون نمبر", labelLocation: "مقام",
    btnDelete: "حذف کریں", btnWithdraw: "واپس لیں",
    labelSkills: "آپ کی مہارتیں",
    availableJobsTitle: "دستیاب نوکریاں", myApplicationsTitle: "میری درخواستیں",
    labelJobTitle: "نوکری کا عنوان", labelRequiredSkills: "مطلوبہ مہارتیں",
    labelJobType: "قسم", labelContact: "رابطہ کی معلومات",
    postJobTitle: "نئی نوکری پوسٹ کریں", btnPostJob: "نوکری پوسٹ کریں", myJobsTitle: "میری پوسٹ کردہ نوکریاں",

    assistantHeading: "معاون سے پوچھیں",
    assistantDesc: "پلیٹ فارم کے بارے میں آسان زبان میں کچھ بھی پوچھیں - یہ آپ کو صحیح ٹول تک رہنمائی کرے گا۔",
    assistantPlaceholder: "مثلاً میں کیسے چیک کروں کہ میں کسی اسکیم کا اہل ہوں؟",
    btnSend: "بھیجیں",
  },
};
