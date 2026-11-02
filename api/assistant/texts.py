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
        "en": "I don't have \"{text}\" in my guide yet, so I won't guess at it. Try saying it another way, ask a person on our team, or pick one of these:",
        "am": "\"{text}\" እስካሁን በመመሪያዬ ውስጥ የለም፤ ስለዚህ አልገምትም። በሌላ መንገድ ይግለጹት፣ የቡድናችንን ሰው ይጠይቁ፣ ወይም ከእነዚህ አንዱን ይምረጡ፦",
    },
    "did_you_mean": {"en": "Did you mean {title}?", "am": "{title} ማለትዎ ነው?"},
    "not_found_long": {
        "en": "I don't have that service in my guide yet, so I won't guess at it. Try naming just the service (for example \"trade license\"), ask a person on our team, or pick one of these:",
        "am": "ያንን አገልግሎት እስካሁን በመመሪያዬ ውስጥ የለም፤ ስለዚህ አልገምትም። የአገልግሎቱን ስም ብቻ ይጻፉ (ለምሳሌ \"የንግድ ፈቃድ\")፣ የቡድናችንን ሰው ይጠይቁ፣ ወይም ከእነዚህ አንዱን ይምረጡ፦",
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
    "hire_none_type": {
        "en": "No verified {plural} are listed yet, and I won't send you to someone we haven't checked. Post a request on the Hire page, or ask our team to find one for you.",
        "am": "እስካሁን የተረጋገጡ {plural} አልተመዘገቡም፤ ያልፈተሽነውን ሰው አልጠቁምዎትም። በቅጥር ገጹ ላይ ጥያቄ ያቅርቡ፣ ወይም ቡድናችን እንዲያገኝልዎ ይጠይቁ።",
    },
    "business_forms": {
        "en": "The main business forms, in short (general information from the Commercial Code, Proclamation 1243/2021):\n"
              "• Sole proprietor: you alone own the business. Simplest to register, but you are personally liable "
              "for its debts, including with your own property. While yearly sales stay under 2 million ETB you "
              "may be taxed on the simpler presumptive (Category B) rules.\n"
              "• Private limited company (PLC): a company separate from you, with one owner (one-member PLC) or "
              "several. Owners risk only what they put in. It reserves a trade name, has its memorandum and articles "
              "authenticated, keeps proper books from day one and pays 30% tax on profit.\n"
              "• Share company: for larger businesses that raise money from many shareholders. More rules, "
              "usually set up with a lawyer.\n"
              "Which one fits depends on your risk, partners, capital and plans. This is general information, "
              "not legal or tax advice; a licensed advisor can look at your case.",
        "am": "ዋና ዋናዎቹ የንግድ አደረጃጀቶች በአጭሩ (አጠቃላይ መረጃ ከንግድ ሕግ፣ አዋጅ ቁጥር 1243/2013)፦\n"
              "• የግል ነጋዴ፦ ንግዱ የእርስዎ ብቻ ነው። ለመመዝገብ ቀላሉ ነው፤ ግን ለንግዱ ዕዳ በግል ንብረትዎ ጭምር ኃላፊ ነዎት። "
              "ዓመታዊ ሽያጭዎ ከ2 ሚሊዮን ብር በታች እስከሆነ በቀላሉ የግምት (ደረጃ ለ) ግብር ሊከፍሉ ይችላሉ።\n"
              "• ኃላፊነቱ የተወሰነ የግል ማህበር (ኃ/የተ/የግ/ማ)፦ ከእርስዎ የተለየ ድርጅት ነው፤ አንድ ባለቤት (የአንድ ሰው ኃ/የተ/የግ/ማ) "
              "ወይም ብዙ ሊኖሩት ይችላል። ባለቤቶች የሚያጡት ያዋጡትን ብቻ ነው። የንግድ ስም ያስይዛል፣ የመመስረቻ ጽሑፉንና መተዳደሪያ ደንቡን "
              "ያስረጋግጣል፣ ከመጀመሪያው ቀን ትክክለኛ የሂሳብ መዝገብ ይይዛል፣ ከትርፉ 30% ግብር ይከፍላል።\n"
              "• አክሲዮን ማህበር፦ ከብዙ ባለአክሲዮኖች ገንዘብ ለሚያሰባስቡ ትላልቅ ንግዶች። ብዙ ደንቦች አሉት፤ ብዙውን ጊዜ በጠበቃ ይቋቋማል።\n"
              "የሚስማማዎት እንደ አደጋው፣ አጋሮችዎ፣ ካፒታልዎና ዕቅድዎ ይወሰናል። ይህ አጠቃላይ መረጃ እንጂ የሕግ ወይም የግብር ምክር አይደለም፤ "
              "ፈቃድ ያለው አማካሪ ጉዳይዎን ሊያይ ይችላል።",
    },
    "hire_none": {"en": "No verified provider lists this service yet. You can still post a request on the Hire page.", "am": "ይህን አገልግሎት የሚሰጥ የተረጋገጠ አገልግሎት ሰጪ እስካሁን የለም። በቅጥር ገጹ ላይ ጥያቄ ማቅረብ ይችላሉ።"},
    "multi_entity": {
        "en": "For two or more linked companies, each company is registered on its own (commercial registration, TIN, trade license), and the link between them is recorded in the memorandum of association. I can show the commercial registration path, or find an agency that handles group structures.",
        "am": "ለሁለት ወይም ከዚያ በላይ የተያያዙ ድርጅቶች እያንዳንዱ ድርጅት ራሱን ችሎ ይመዘገባል (የንግድ ምዝገባ፣ ቲን፣ የንግድ ፈቃድ)፤ በመካከላቸው ያለው ግንኙነት በመመስረቻ ጽሑፉ ላይ ይመዘገባል። የንግድ ምዝገባ መንገዱን ላሳይዎ ወይም ይህን የሚያስፈጽም ኤጀንሲ ላገኝልዎ እችላለሁ።",
    },
    # Starting a business: general information about the steps, never advice on the person's own case
    "start_business": {
        "en": "Starting a business in Ethiopia usually goes in this order:\n"
              "1. Choose the business form: sole proprietor (you alone), private limited company (PLC, "
              "also one-member PLC) or share company. A PLC first reserves its trade name and has its "
              "memorandum and articles of association authenticated.\n"
              "2. Get a TIN (taxpayer number) from the Ministry of Revenues.\n"
              "3. Register with the Ministry of Trade and Regional Integration (commercial registration).\n"
              "4. Get the trade licence, within one year of registering. Some sectors (for example health, "
              "education, finance, import and export) first need a certificate of competence from their regulator.\n"
              "Source: Commercial Registration and Business Licensing Proclamation No. 980/2016, amended by No. 1150/2019.\n\n"
              "This is general information about the steps, not legal or tax advice. Which form fits you "
              "depends on your partners, your capital and how you will be taxed, so a licensed tax agent "
              "or accountant can look at your case. Pick a step to see its documents, fees and offices.",
        "am": "በኢትዮጵያ ንግድ መጀመር በአብዛኛው በዚህ ቅደም ተከተል ይሄዳል፦\n"
              "1. የንግድ አይነቱን ይምረጡ፦ የግል ነጋዴ (እርስዎ ብቻ)፣ ኃላፊነቱ የተወሰነ የግል ማህበር (ኃ/የተ/የግ/ማ፣ "
              "የአንድ ሰው ኃ/የተ/የግ/ማም ጭምር) ወይም አክሲዮን ማህበር። ኃ/የተ/የግ/ማ መጀመሪያ የንግድ ስሙን ያስይዛል፤ "
              "የመመስረቻ ጽሑፉንና መተዳደሪያ ደንቡን ያስረጋግጣል።\n"
              "2. ከገቢዎች ሚኒስቴር ቲን (የግብር ከፋይ መለያ ቁጥር) ያውጡ።\n"
              "3. በንግድና ቀጠናዊ ትስስር ሚኒስቴር ይመዝገቡ (የንግድ ምዝገባ)።\n"
              "4. ከተመዘገቡ በአንድ ዓመት ውስጥ የንግድ ፈቃድ ያውጡ። አንዳንድ ዘርፎች (ለምሳሌ ጤና፣ ትምህርት፣ ፋይናንስ፣ "
              "ወጪና ገቢ ንግድ) አስቀድመው ከተቆጣጣሪያቸው የብቃት ማረጋገጫ ይፈልጋሉ።\n"
              "ምንጭ፦ የንግድ ምዝገባና ፈቃድ አዋጅ ቁጥር 980/2008 (በአዋጅ ቁጥር 1150/2011 እንደተሻሻለ)።\n\n"
              "ይህ ስለ ደረጃዎቹ አጠቃላይ መረጃ ነው እንጂ የሕግ ወይም የግብር ምክር አይደለም። የትኛው አይነት እንደሚስማማዎ "
              "በአጋሮችዎ፣ በካፒታልዎና በሚከፍሉት ግብር ይወሰናል፤ ፈቃድ ያለው የታክስ ወኪል ወይም የሂሳብ ባለሙያ ጉዳይዎን "
              "ሊያይልዎ ይችላል። ሰነዶቹን፣ ክፍያዎቹንና ቢሮዎቹን ለማየት አንድ ደረጃ ይምረጡ።",
    },
    "start_costs_head": {
        "en": "What the offices charge for each step, from our records. None of these amounts has been confirmed "
              "by the office yet, so check the fee at the window before you pay:",
        "am": "እያንዳንዱ ደረጃ በቢሮዎቹ የሚያስከፍለው፣ ከመዝገባችን። ከእነዚህ ክፍያዎች አንዳቸውም ገና በቢሮው አልተረጋገጡም፤ "
              "ከመክፈልዎ በፊት በመስኮቱ ላይ ያረጋግጡ፦",
    },
    "start_costs_tail": {
        "en": "Fees can differ between sub-cities and with your capital and activity. A PLC also pays to authenticate "
              "its memorandum and articles at the Documents Authentication and Registration Service. Budget too for a "
              "notarised lease for your premises, any sector certificate of competence, and an accountant.\n"
              "Pay official fees only at the office window or through the office's own payment channel, never to a person.",
        "am": "ክፍያዎቹ በክፍለ ከተማና በካፒታልዎና በሥራ ዘርፍዎ ሊለያዩ ይችላሉ። ኃ/የተ/የግ/ማ የመመስረቻ ጽሑፉንና መተዳደሪያ "
              "ደንቡን በሰነዶች ማረጋገጫና ምዝገባ አገልግሎት ለማስረጋገጥም ይከፍላል። ለሥራ ቦታዎ የተረጋገጠ የኪራይ ውል፣ "
              "ለዘርፍዎ የብቃት ማረጋገጫ ካስፈለገ፣ እና ለሂሳብ ባለሙያም በጀት ይያዙ።\n"
              "ኦፊሴላዊ ክፍያዎችን በቢሮው መስኮት ወይም በቢሮው የራሱ የክፍያ መንገድ ብቻ ይክፈሉ፤ ለግለሰብ በፍጹም አይክፈሉ።",
    },
    # Checked against Income Tax (Amendment) Proclamation No. 1395/2025, VAT Proclamation No. 1341/2024 and the
    # private-sector pension law on 2026-11-01. Rates and thresholds change: review this text every year.
    "business_taxes": {
        "en": "The taxes a new business has to deal with (general information, checked 1 Nov 2026):\n"
              "• Every company (PLC, share company) is a Category A taxpayer from the first day: it keeps proper books "
              "and pays 30% tax on its profit. A sole proprietor becomes Category A once yearly sales pass 2 million ETB.\n"
              "• Smaller sole proprietors (Category B) pay a presumptive tax worked out from their yearly sales, "
              "instead of keeping full books.\n"
              "• VAT is 15%. You must register once your taxable sales pass 2 million ETB in any 12 months. A "
              "VAT-registered business files a return every month, including months with no sales.\n"
              "• If you employ people, you withhold their income tax every month and pay their pension: 7% from "
              "the employee and 11% from you.\n"
              "• The trade licence is renewed every year. Late renewals and late tax filings bring penalties and interest.\n"
              "• Stopping work does not end these duties. Close the business formally and settle your TIN account.\n"
              "Sources: Income Tax (Amendment) Proclamation No. 1395/2025, VAT Proclamation No. 1341/2024, Private "
              "Organization Employees' Pension Proclamation No. 715/2011.\n\n"
              "This is general information, not tax advice. What applies to you depends on your business, so a "
              "licensed tax agent should check your case before you register.",
        "am": "አዲስ ንግድ የሚመለከታቸው ግብሮች (አጠቃላይ መረጃ፣ ኖቬምበር 1 ቀን 2026 የተረጋገጠ)፦\n"
              "• ማንኛውም ድርጅት (ኃ/የተ/የግ/ማ፣ አክሲዮን ማህበር) ከመጀመሪያው ቀን የደረጃ ሀ ግብር ከፋይ ነው፤ ትክክለኛ የሂሳብ "
              "መዝገብ ይይዛል፤ ከትርፉ 30% ግብር ይከፍላል። የግል ነጋዴ ዓመታዊ ሽያጩ ከ2 ሚሊዮን ብር ሲያልፍ ደረጃ ሀ ይሆናል።\n"
              "• አነስተኛ የግል ነጋዴዎች (ደረጃ ለ) ሙሉ መዝገብ ከመያዝ ይልቅ ከዓመታዊ ሽያጫቸው በሚሰላ የግምት ግብር ይከፍላሉ።\n"
              "• ተጨማሪ እሴት ታክስ (ቫት) 15% ነው። በማንኛውም 12 ወራት ውስጥ ታክስ የሚከፈልበት ሽያጭዎ ከ2 ሚሊዮን ብር ካለፈ "
              "መመዝገብ ግዴታ ነው። በቫት የተመዘገበ ንግድ ሽያጭ በሌለበት ወርም ጭምር በየወሩ ያሳውቃል።\n"
              "• ሠራተኛ ከቀጠሩ የገቢ ግብራቸውን በየወሩ ቀንሰው ያስገባሉ፤ የጡረታ መዋጮም ይከፍላሉ፦ ከሠራተኛው 7%፣ ከእርስዎ 11%።\n"
              "• የንግድ ፈቃድ በየዓመቱ ይታደሳል። ዘግይቶ ማደስና ዘግይቶ ግብር ማሳወቅ ቅጣትና ወለድ ያስከትላል።\n"
              "• ሥራ ማቆም እነዚህን ግዴታዎች አያስቀርም። ንግዱን በሕጋዊ መንገድ ይዝጉ፤ የቲን ሂሳብዎን ያወራርዱ።\n"
              "ምንጭ፦ የገቢ ግብር (ማሻሻያ) አዋጅ ቁጥር 1395/2017፣ የተጨማሪ እሴት ታክስ አዋጅ ቁጥር 1341/2016፣ የግል ድርጅት "
              "ሠራተኞች የጡረታ አዋጅ ቁጥር 715/2003።\n\n"
              "ይህ አጠቃላይ መረጃ ነው እንጂ የግብር ምክር አይደለም። የሚመለከትዎ በንግድዎ ይወሰናል፤ ከመመዝገብዎ በፊት ፈቃድ ያለው "
              "የታክስ ወኪል ጉዳይዎን ይመልከት።",
    },
    # Investment advice needs a licence from the Ethiopian Capital Market Authority (Proclamation No.
    # 1248/2021), and automated advice a separate robo-adviser licence. The assistant never gives it.
    "no_investment_advice": {
        "en": "I can't advise you on what to invest in or which shares to buy. In Ethiopia only investment "
              "advisers licensed by the Ethiopian Capital Market Authority (ECMA) may give that advice. "
              "I can help with the office side of a business: registration, TIN, trade licence and tax "
              "filing, or find you a verified tax agent or accountant.",
        "am": "በምን ኢንቨስት እንደሚያደርጉ ወይም የትኛውን አክሲዮን እንደሚገዙ ልመክርዎ አልችልም። በኢትዮጵያ ይህን ምክር "
              "መስጠት የሚችሉት በኢትዮጵያ ካፒታል ገበያ ባለስልጣን ፈቃድ ያገኙ የኢንቨስትመንት አማካሪዎች ብቻ ናቸው። "
              "በንግዱ የቢሮ ጉዳዮች ማለትም ምዝገባ፣ ቲን፣ የንግድ ፈቃድና የግብር ማሳወቅ ላግዝዎ ወይም የተረጋገጠ የታክስ ወኪል "
              "ወይም የሂሳብ ባለሙያ ላገኝልዎ እችላለሁ።",
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
    "advisor": {"en": "Find a tax or business advisor", "am": "የታክስ ወይም የንግድ አማካሪ ፈልግ"},
    "start_costs": {"en": "What will it cost?", "am": "ስንት ያስከፍላል?"},
    "business_forms": {"en": "PLC or sole proprietor?", "am": "ኃ/የተ/የግ/ማ ወይስ የግል ነጋዴ?"},
    "vat_registration": {"en": "VAT registration", "am": "የተጨማሪ እሴት ታክስ ምዝገባ"},
    "talk_to_person": {"en": "Ask a person", "am": "ሰው ልጠይቅ"},
    "business_taxes": {"en": "Taxes I'll pay", "am": "የምከፍላቸው ግብሮች"},
    "commercial_registration": {"en": "Commercial registration", "am": "የንግድ ምዝገባ"},
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
