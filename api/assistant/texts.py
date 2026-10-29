"""Reply templates in English and Amharic. Facts are filled in from our data, never written here."""

T: dict[str, dict[str, str]] = {
    "welcome": {
        "en": "Hello! I can show you exactly what to do for any service: which offices, in which order, what to bring and what it costs. I can also find you a verified agent. What do you need to get done?",
        "am": "ሰላም! ለማንኛውም አገልግሎት ምን ማድረግ እንዳለብዎ አሳይዎታለሁ፦ የትኞቹ ቢሮዎች፣ በምን ቅደም ተከተል፣ ምን ይዘው እንደሚሄዱ እና ስንት እንደሚያስከፍል። የተረጋገጠ ወኪልም ላገኝልዎ እችላለሁ። ምን ማስፈጸም ይፈልጋሉ?",
    },
    "thanks": {"en": "You're welcome. Anything else I can help with?", "am": "ምንም አይደለም። ሌላ የምረዳዎት ነገር አለ?"},
    "goodbye": {"en": "Good luck with your application. Come back any time.", "am": "መልካም ዕድል። በማንኛውም ጊዜ ይመለሱ።"},
    "smalltalk": {
        "en": "I'm the Compliance Navigator assistant. I know the requirements of many organizations and how they connect, so I can build your step-by-step path and answer questions about fees, documents, time and offices. Tell me a service, for example \"renew my passport\" or \"get a trade license\".",
        "am": "እኔ የኮምፕላያንስ ናቪጌተር ረዳት ነኝ። የብዙ ተቋማትን መስፈርቶች እና እንዴት እንደሚገናኙ አውቃለሁ፤ ስለዚህ ደረጃ በደረጃ መንገድዎን አዘጋጃለሁ፤ ስለ ክፍያ፣ ሰነዶች፣ ጊዜ እና ቢሮዎች እመልሳለሁ። አገልግሎቱን ይንገሩኝ፣ ለምሳሌ \"ፓስፖርት ማሳደስ\" ወይም \"የንግድ ፈቃድ ማውጣት\"።",
    },
    "out_of_scope": {
        "en": "That is outside what I can help with. I help with government and organization services, and with hiring a verified agent. Try one of these:",
        "am": "ያ ከምረዳበት ውጭ ነው። በመንግሥት እና በተቋማት አገልግሎቶች እንዲሁም የተረጋገጠ ወኪል በመቅጠር እረዳለሁ። ከእነዚህ አንዱን ይሞክሩ፦",
    },
    "start_over": {"en": "Sure, let's start again. What do you need to get done?", "am": "እሺ፣ እንደገና እንጀምር። ምን ማስፈጸም ይፈልጋሉ?"},
    "not_found": {
        "en": "I couldn't find a service matching \"{text}\". Could you say it another way, or pick one of these?",
        "am": "\"{text}\" የሚል አገልግሎት አላገኘሁም። በሌላ መንገድ ሊገልጹት ወይም ከእነዚህ አንዱን ሊመርጡ ይችላሉ?",
    },
    "which_service": {"en": "Which service do you mean?", "am": "የትኛውን አገልግሎት ማለትዎ ነው?"},
    "which_passport": {"en": "Which passport service do you need?", "am": "የትኛው የፓስፖርት አገልግሎት ያስፈልግዎታል?"},
    "got_service": {"en": "{title}. Let me ask a few quick questions so the steps fit your situation.", "am": "{title}። ደረጃዎቹ ለእርስዎ ሁኔታ እንዲስማሙ ጥቂት ጥያቄዎች ልጠይቅ።"},
    "ask_sub_city": {"en": "Which sub-city are you in? I'll point you to the right branch.", "am": "በየትኛው ክፍለ ከተማ ነዎት? ትክክለኛውን ቅርንጫፍ እጠቁምዎታለሁ።"},
    "ask_held": {
        "en": "Do you already have any of these? Tick them and I'll skip those steps.",
        "am": "ከእነዚህ ውስጥ ያለዎት አለ? ምልክት ያድርጉ፣ እነዚያን ደረጃዎች እዘላለሁ።",
    },
    "ask_applicant": {"en": "The fee depends on who is applying. Which fits you?", "am": "ክፍያው በአመልካቹ ይለያያል። የትኛው ይስማማዎታል?"},
    "path_intro": {
        "en": "Here is your path for {title}{where}: {steps} step(s) across {offices} office(s){days}.",
        "am": "ለ{title}{where} መንገድዎ ይኸው፦ በ{offices} ቢሮ(ዎች) {steps} ደረጃ(ዎች){days}።",
    },
    "path_done": {
        "en": "You already have everything this path needs. Go straight to the last office with your documents.",
        "am": "ይህ መንገድ የሚፈልገውን ሁሉ ይዘዋል። ሰነዶችዎን ይዘው በቀጥታ ወደ መጨረሻው ቢሮ ይሂዱ።",
    },
    "service_intro": {"en": "Here is what you need for {title}.", "am": "ለ{title} የሚያስፈልግዎ ይኸው።"},
    "missing_docs": {"en": "Still to get: {docs}.", "am": "ገና የሚያስፈልጉ፦ {docs}።"},
    "all_docs": {"en": "You have every document on the list.", "am": "በዝርዝሩ ያሉትን ሰነዶች በሙሉ ይዘዋል።"},
    "ineligible": {"en": "Based on your answers you can't apply for this service: {reasons}", "am": "በመልሶችዎ መሰረት ለዚህ አገልግሎት ማመልከት አይችሉም፦ {reasons}"},
    "next_actions": {"en": "What would you like to do next?", "am": "ቀጥሎ ምን ማድረግ ይፈልጋሉ?"},
    "need_service_first": {"en": "Which service is this about?", "am": "ይህ ስለ የትኛው አገልግሎት ነው?"},
    "fee": {"en": "Fee for {title}: {fee}.", "am": "የ{title} ክፍያ፦ {fee}።"},
    "fee_unknown": {"en": "No fee is recorded for {title} yet. Please confirm at the office before paying.", "am": "ለ{title} የተመዘገበ ክፍያ እስካሁን የለም። ከመክፈልዎ በፊት ቢሮው ላይ ያረጋግጡ።"},
    "documents": {"en": "To apply for {title}, bring:", "am": "ለ{title} ለማመልከት ይዘው የሚሄዱት፦"},
    "documents_none": {"en": "No documents are listed for {title}.", "am": "ለ{title} የተዘረዘረ ሰነድ የለም።"},
    "time": {"en": "Processing time for {title}: {time}.", "am": "የ{title} ማስፈጸሚያ ጊዜ፦ {time}።"},
    "time_unknown": {"en": "No processing time is recorded for {title} yet.", "am": "ለ{title} የተመዘገበ ጊዜ እስካሁን የለም።"},
    "location": {"en": "Where to go for {title}:", "am": "ለ{title} የሚሄዱበት ቦታ፦"},
    "location_unknown": {"en": "No office address is recorded for {title} yet.", "am": "ለ{title} የተመዘገበ የቢሮ አድራሻ እስካሁን የለም።"},
    "online_yes": {"en": "Part of {title} can be done online: {url}", "am": "የ{title} ከፊል ሂደት በኦንላይን ይቻላል፦ {url}"},
    "online_no": {"en": "No online option is recorded for {title}; plan to go in person.", "am": "ለ{title} የተመዘገበ የኦንላይን አማራጭ የለም፤ በአካል ለመሄድ ያቅዱ።"},
    "proxy_yes": {"en": "Someone else can apply for you{notes}.", "am": "ሌላ ሰው ሊያመለክትልዎ ይችላል{notes}።"},
    "proxy_poa": {"en": "Someone else can apply for you with a notarized power of attorney{notes}.", "am": "በተረጋገጠ ውክልና ሌላ ሰው ሊያመለክትልዎ ይችላል{notes}።"},
    "proxy_no": {"en": "You must apply in person for {title}{notes}.", "am": "ለ{title} በአካል ማመልከት አለብዎ{notes}።"},
    "proxy_unknown": {
        "en": "{title} does not say whether someone else can apply for you. Ask the office, or hire a verified agent who knows the rules.",
        "am": "{title} ሌላ ሰው ሊያመለክትልዎ ይችል እንደሆነ አልገለጸም። ቢሮውን ይጠይቁ ወይም ደንቡን የሚያውቅ የተረጋገጠ ወኪል ይቅጠሩ።",
    },
    "hire": {"en": "Verified providers who can handle {title} for you:", "am": "{title}ን ሊያስፈጽሙልዎ የሚችሉ የተረጋገጡ አገልግሎት ሰጪዎች፦"},
    "hire_any": {"en": "Verified providers you can hire:", "am": "ሊቀጥሯቸው የሚችሉ የተረጋገጡ አገልግሎት ሰጪዎች፦"},
    "no_brokers": {
        "en": "We don't list property or car brokers (delala). Compliance Navigator is for getting things done with offices: licences, permits, IDs, tax and documents. If you're buying or renting, I can still show you the office side, for example a title deed transfer, a lease registration or a vehicle ownership transfer.",
        "am": "የቤት ወይም የመኪና ደላሎችን አንዘረዝርም። ኮምፕላያንስ ናቪጌተር ከቢሮዎች ጋር ጉዳይ ለማስፈጸም ነው፦ ፈቃዶች፣ መታወቂያዎች፣ ግብር እና ሰነዶች። እየገዙ ወይም እየተከራዩ ከሆነ የቢሮውን ክፍል ላሳይዎ እችላለሁ፤ ለምሳሌ የካርታ ስም ዝውውር፣ የኪራይ ውል ምዝገባ ወይም የተሽከርካሪ ባለቤትነት ዝውውር።",
    },
    "hire_none": {"en": "No verified provider lists this service yet. You can still post a request on the Hire page.", "am": "ይህን አገልግሎት የሚሰጥ የተረጋገጠ አገልግሎት ሰጪ እስካሁን የለም። በቅጥር ገጹ ላይ ጥያቄ ማቅረብ ይችላሉ።"},
    "multi_entity": {
        "en": "For two or more linked companies, each company is registered on its own (commercial registration, TIN, trade license), and the link between them is recorded in the memorandum of association. I can show the commercial registration path, or find an agency that handles group structures.",
        "am": "ለሁለት ወይም ከዚያ በላይ የተያያዙ ድርጅቶች እያንዳንዱ ድርጅት ራሱን ችሎ ይመዘገባል (የንግድ ምዝገባ፣ ቲን፣ የንግድ ፈቃድ)፤ በመካከላቸው ያለው ግንኙነት በመመስረቻ ጽሑፉ ላይ ይመዘገባል። የንግድ ምዝገባ መንገዱን ላሳይዎ ወይም ይህን የሚያስፈጽም ኤጀንሲ ላገኝልዎ እችላለሁ።",
    },
    "resume": {"en": "Good, let's pick up from where you are.", "am": "ጥሩ፣ ካሉበት እንቀጥል።"},
    "language_choice": {"en": "Would you like me to reply in English or Amharic?", "am": "በእንግሊዝኛ ወይስ በአማርኛ ልመልስልዎ?"},
    "answer_free_text": {"en": "Please type your answer.", "am": "እባክዎ መልስዎን ይጻፉ።"},
    "source": {"en": "Source: {source}", "am": "ምንጭ፦ {source}"},
    "src_org": {"en": "published by {org}", "am": "በ{org} የቀረበ"},
    "src_path": {"en": "Compliance Navigator path data", "am": "የኮምፕላያንስ ናቪጌተር የመንገድ መረጃ"},
    "src_mesob": {"en": "MESOB catalog (partner)", "am": "የመሶብ ካታሎግ (አጋር)"},
}

CHIPS: dict[str, dict[str, str]] = {
    "passport": {"en": "Passport", "am": "ፓስፖርት"},
    "trade_license": {"en": "Trade license", "am": "የንግድ ፈቃድ"},
    "tin": {"en": "TIN certificate", "am": "ቲን"},
    "kebele_id": {"en": "Kebele ID", "am": "የቀበሌ መታወቂያ"},
    "hire": {"en": "Hire an agent", "am": "ወኪል ልቅጠር"},
    "fee": {"en": "How much is it?", "am": "ስንት ያስከፍላል?"},
    "documents": {"en": "What do I bring?", "am": "ምን ይዤ ልሂድ?"},
    "time": {"en": "How long does it take?", "am": "ስንት ጊዜ ይፈጃል?"},
    "location": {"en": "Where do I go?", "am": "የት ልሂድ?"},
    "online": {"en": "Can I do it online?", "am": "በኦንላይን ይቻላል?"},
    "proxy": {"en": "Can someone apply for me?", "am": "ሌላ ሰው ሊያመለክትልኝ ይችላል?"},
    "start_over": {"en": "Start over", "am": "እንደገና ጀምር"},
    "continue": {"en": "Continue", "am": "ቀጥል"},
    "none_held": {"en": "I have none of these", "am": "አንዱም የለኝም"},
    "yes": {"en": "Yes", "am": "አዎ"},
    "no": {"en": "No", "am": "አይ"},
    "english": {"en": "English", "am": "English"},
    "amharic": {"en": "አማርኛ", "am": "አማርኛ"},
    "open_path": {"en": "Open full path", "am": "ሙሉ መንገዱን ክፈት"},
    "view_service": {"en": "View service page", "am": "የአገልግሎቱን ገጽ ይመልከቱ"},
    "hire_for": {"en": "Hire someone to do it", "am": "የሚያስፈጽምልኝ ልቅጠር"},
    "report": {"en": "Report wrong information", "am": "የተሳሳተ መረጃ ሪፖርት አድርግ"},
    "map": {"en": "Show on map", "am": "በካርታ አሳይ"},
    "applicant_ethiopian": {"en": "Ethiopian citizen", "am": "ኢትዮጵያዊ"},
    "applicant_foreign": {"en": "Foreign national", "am": "የውጭ ዜጋ"},
    "applicant_company": {"en": "Company", "am": "ድርጅት"},
}


def t(key: str, lang: str, **kw) -> str:
    entry = T[key]
    text = entry.get(lang) or entry["en"]
    return text.format(**kw) if kw else text


def chip(key: str, lang: str) -> str:
    entry = CHIPS[key]
    return entry.get(lang) or entry["en"]
