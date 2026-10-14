# EXISTING AWARDS INDEX — duplicate check for the bachelor batch

Generated 2026-10-03T14:51:01.456Z from programme_details.json, new_scholarships.json,
purged_records_archive.json, retired_records.json, record_corrections.json,
official_logo_overrides.json, verification_confirmations.json, official_programme_facts.json, phase2_audit_report.json.

**Run this check BEFORE writing any record.**

```bash
# is the awarding body already indexed?
node -e "const i=require('./research/bachelor/EXISTING_AWARDS.json');
const d=process.argv[1];const h=i.byDomain[d]||[];
console.log(h.length?h.map(a=>[a.state,a.id,a.name||'(untitled)'].join(' | ')).join('\n'):'CLEAR - no existing award on this domain')" \
  duke.edu
```

| metric | count |
|---|---|
| awards_indexed | 529 |
| live | 368 |
| pending_insert | 87 |
| purged | 62 |
| retired | 4 |
| corrected | 8 |
| distinct_hosts | 387 |
| distinct_reg_domains | 288 |
| logo_hosts | 357 |
| titled | 518 |
| untitled | 11 |

## Awards that already include Bachelor's level (162)

| id | state | name | source |
|---|---|---|---|
| 3 | LIVE | DAAD Scholarship | programme_details.json |
| 4 | LIVE | Global Korea Scholarship (GKS) | programme_details.json |
| 8 | LIVE | France Excellence Charpak Scholarship Program | programme_details.json |
| 10 | LIVE | Deutschlandstipendium (Germany Scholarship) | programme_details.json |
| 12 | LIVE | JASSO Monbukagakusho Honors Scholarship | programme_details.json |
| 17 | LIVE | Erasmus+ Student Exchange (Studying Abroad) | programme_details.json |
| 25 | LIVE | JASSO Student Exchange Support Program | programme_details.json |
| 26 | LIVE | Global Korea Scholarship (GKS) Non-degree Exchange Program | programme_details.json |
| 30 | LIVE | Australia Awards Scholarships | programme_details.json |
| 32 | LIVE | Swedish Institute Scholarship | programme_details.json |
| 34 | LIVE | Taiwan Scholarship Program | programme_details.json |
| 39 | LIVE | Pearson International Scholarship (University of Toronto) | programme_details.json |
| 40 | LIVE | ARES Scholarships (Belgium) | programme_details.json |
| 43 | LIVE | Australia Awards Fellowships | programme_details.json |
| 48 | LIVE | University of Sydney Vice-Chancellor's International Scholarships Scheme | programme_details.json |
| 49 | LIVE | Annie Farrand Scholarship in Agricultural Science (International) | programme_details.json |
| 52 | LIVE | Monash International Leadership Scholarship | programme_details.json |
| 54 | LIVE | University of Miami Stamps Scholarship | programme_details.json |
| 55 | LIVE | American University Emerging Global Leader Scholarship | programme_details.json |
| 56 | LIVE | Jefferson Scholars Foundation Scholarship | programme_details.json |
| 57 | LIVE | King-Morgridge Scholars Program | programme_details.json |
| 58 | LIVE | Brandeis University Wien International Scholarship | programme_details.json |
| 59 | LIVE | University of Minnesota Global Excellence Scholarship | programme_details.json |
| 61 | LIVE | Clark University Presidential Scholarship | programme_details.json |
| 63 | LIVE | Michigan State University International Merit Scholarships | programme_details.json |
| 64 | LIVE | University of Oregon International Cultural Service Program | programme_details.json |
| 81 | LIVE | Study in Canada Scholarships (SICS) | programme_details.json |
| 83 | LIVE | McCall MacBain Scholarships at McGill University | programme_details.json |
| 84 | LIVE | UBC International Major Entrance Scholarship (IMES) | programme_details.json |
| 85 | LIVE | Karen McKellin International Leader of Tomorrow Award (UBC) | programme_details.json |
| 87 | LIVE | McMaster University Award of Excellence (International) | programme_details.json |
| 90 | LIVE | University of Waterloo International Student Entrance Scholarship | programme_details.json |
| 105 | LIVE | NUS International Undergraduate Scholarship | programme_details.json |
| 106 | LIVE | NTU Nanyang Global Scholarship | programme_details.json |
| 110 | LIVE | QUAD STEM Scholarship Scheme (ICCR) | programme_details.json |
| 120 | LIVE | Alan and Jane Handler Endowed Scholarship — University of Rochester | programme_details.json |
| 121 | LIVE | Berea College Tuition Promise Scholarship | programme_details.json |
| 122 | LIVE | Karsh International Scholars Program — Duke University | programme_details.json |
| 123 | LIVE | Gabelli Presidential Scholars Program — Boston College | programme_details.json |
| 125 | LIVE | Harvard University Financial Aid (International) | programme_details.json |
| 127 | LIVE | Princeton University Financial Aid (International) | programme_details.json |
| 132 | LIVE | #YouAreWelcomeHere Scholarship | programme_details.json |
| 136 | LIVE | University of Padua — Padua International Excellence Scholarship | programme_details.json |
| 138 | LIVE | University of Milano-Bicocca — BISP (Bicocca International Scholarship Programme) | programme_details.json |
| 139 | LIVE | Bocconi University — ISU Bocconi Scholarship / Bocconi4Access to Education | programme_details.json |
| 142 | LIVE | University of Brescia — STAR Scholarships (Foundation Year + Bachelor's) | programme_details.json |
| 144 | LIVE | MOFA Taiwan Scholarship | programme_details.json |
| 149 | LIVE | NTHU International Student Scholarship | programme_details.json |
| 154 | LIVE | University of St.Gallen (HSG) Excellence Scholarships for Bachelor Students | programme_details.json |
| 160 | LIVE | University of Basel Financial Aid and Scholarships | programme_details.json |
| 161 | LIVE | WIPO Fellowship Program | programme_details.json |
| 163 | LIVE | TU Wien Scholarships for International Students | programme_details.json |
| 165 | LIVE | University of Innsbruck Scholarships for International Students | programme_details.json |
| 170 | LIVE | Webster University Vienna Scholarships | programme_details.json |
| 171 | LIVE | Modul University Vienna Scholarships | programme_details.json |
| 175 | LIVE | Erasmus University Rotterdam (EUR) — Holland Scholarship & Talent Programmes | programme_details.json |
| 183 | LIVE | Lund University Global Scholarship | programme_details.json |
| 189 | LIVE | Umeå University Scholarship for International Students | programme_details.json |
| 193 | LIVE | Adelaide Academic Excellence Scholarship (50%) | programme_details.json |
| 194 | LIVE | UQ International Excellence Scholarship | programme_details.json |
| 200 | LIVE | UTS Vice-Chancellor's International Undergraduate Scholarship | programme_details.json |
| 201 | LIVE | QUT International Merit Scholarship | programme_details.json |
| 202 | LIVE | RMIT Future Leaders Scholarship | programme_details.json |
| 207 | LIVE | La Trobe High Achiever Scholarship | programme_details.json |
| 210 | LIVE | KAIST International Student Scholarship (Undergraduate) | programme_details.json |
| 236 | LIVE | MEXT Scholarship for Undergraduate Students | programme_details.json |
| 240 | LIVE | JASSO Reservation Program for Monbukagakusho Honors Scholarship by Pre-arrival Admission | programme_details.json |
| 246 | LIVE | Nankai University Chinese Government Scholarship - Silk Road Program | programme_details.json |
| 251 | LIVE | Trinity College Dublin Global Excellence Undergraduate Scholarship | programme_details.json |
| 253 | LIVE | University of Galway Global Scholarships | programme_details.json |
| 254 | LIVE | Manaaki New Zealand Scholarships | programme_details.json |
| 258 | LIVE | University of Otago Vice-Chancellor's Scholarship for International Students | programme_details.json |
| 259 | LIVE | University of Otago International Academic Excellence Scholarship | programme_details.json |
| 261 | LIVE | VUW Undergraduate International Scholarship (Victoria University of Wellington) | programme_details.json |
| 263 | LIVE | Aalto University Excellence Scholarship | programme_details.json |
| 266 | LIVE | University of Turku International Scholarships | programme_details.json |
| 268 | LIVE | Danish Government Scholarship for Highly Qualified Non-EU/EEA Students | programme_details.json |
| 276 | LIVE | BI International Baccalaureate Scholarship | programme_details.json |
| 285 | LIVE | Stipendium Hungaricum Scholarship Programme | programme_details.json |
| 286 | LIVE | Hungarian Diaspora Scholarship Programme | programme_details.json |
| 288 | LIVE | Budapest University of Technology and Economics (BME) Scholarships | programme_details.json |
| 292 | LIVE | Jagiellonian University Rector's Scholarship for International Students | programme_details.json |
| 295 | LIVE | Charles University Scholarships — International Students | programme_details.json |
| 302 | LIVE | University of Porto Merit Scholarships and Funding | programme_details.json |
| 311 | LIVE | Canada-ASEAN Scholarships and Educational Exchanges for Development (SEED-2) | programme_details.json |
| 312 | LIVE | Schulich Leader Scholarships | programme_details.json |
| 322 | LIVE | Chinese Government Scholarship (CGS - China Embassy, Dhaka) 2025/2026 | programme_details.json |
| 323 | LIVE | Chinese Government Scholarship (CGS - China Embassy, Jakarta) 2026/2027 | programme_details.json |
| 326 | LIVE | Václav Havel Bursary | programme_details.json |
| 335 | LIVE | Aalto University Excellence Scholarship (100% Tuition Fee Waiver) | programme_details.json |
| 336 | LIVE | Tampere University Scholarships (Tuition Fee Waiver + International Advancement Scholarship) | programme_details.json |
| 356 | LIVE | Hungarian Bilateral State Scholarships | programme_details.json |
| 358 | LIVE | Hungarian Diaspora Scholarship | programme_details.json |
| 359 | LIVE | Semmelweis Pannonia In Excellence Scholarship | programme_details.json |
| 366 | LIVE | DCU International Scholarships for Non-EU Students 2027-28 | programme_details.json |
| 371 | LIVE | University of Bologna Study Grants and Fees | programme_details.json |
| 373 | LIVE | Japanese Government (MEXT) Scholarship 2027 – Undergraduate Students | programme_details.json |
| 376 | LIVE | JASSO Monbukagakusho Honors Scholarship for Privately-Financed International Students | programme_details.json |
| 380 | LIVE | Rotary Yoneyama Memorial Scholarship 2027 (Overseas Candidates) | programme_details.json |
| 381 | LIVE | NL Scholarship (formerly Holland Scholarship) | programme_details.json |
| 399 | LIVE | Tulī Takes Flight Scholarships 2026 | programme_details.json |
| 403 | LIVE | Ngarimu VC and 28th (Māori) Battalion Memorial Scholarships 2026–2027 | programme_details.json |
| 406 | LIVE | University of Auckland Vaka Moana Scholarship 2027 | programme_details.json |
| 407 | LIVE | University of Waikato Vice-Chancellor's International Excellence Scholarship 2026 | programme_details.json |
| 422 | LIVE | UNESCO/Poland Co-Sponsored Fellowships Programme in Engineering | programme_details.json |
| 423 | LIVE | Erasmus+ Programme | programme_details.json |
| 425 | LIVE | CEEPUS Exchange Programme | programme_details.json |
| 428 | LIVE | SAF Merit Scholarship | programme_details.json |
| 429 | LIVE | MHA Civilian Scholarship | programme_details.json |
| 430 | LIVE | Singapore Police Force Scholarship | programme_details.json |
| 431 | LIVE | PSC Undergraduate Scholarship | programme_details.json |
| 434 | LIVE | MOE Teaching Scholarship (Full-Term) | programme_details.json |
| 439 | LIVE | NUS Undergraduate Scholarship (incl. Global Merit, Merit, AI Talent, Sports, Performing & Visual Arts) | programme_details.json |
| 442 | LIVE | SMU Global Impact Scholarship Award | programme_details.json |
| 443 | LIVE | SMU Merit Scholarship | programme_details.json |
| 444 | LIVE | Temasek Undergraduate Overseas Scholarship | programme_details.json |
| 445 | LIVE | Temasek Undergraduate Local Scholarship | programme_details.json |
| 447 | LIVE | SUTD Trailblazers Scholarship | programme_details.json |
| 448 | LIVE | SUSS Scholarship (Part-time Undergraduate) | programme_details.json |
| 450 | LIVE | NTU Short Term Scholarships | programme_details.json |
| 459 | LIVE | EPFL Bachelor Excellence Fellowships | programme_details.json |
| 463 | LIVE | UZH Student Financial Aid Office – Scholarships | programme_details.json |
| 464 | LIVE | EPFL Social Scholarship | programme_details.json |
| 465 | LIVE | Hans Wilsdorf Foundation Scholarship (EPFL) | programme_details.json |
| 466 | LIVE | UZH Hardship Loan | programme_details.json |
| 468 | LIVE | NYCU International Student Scholarship | programme_details.json |
| 476 | LIVE | Benjamin A. Gilman International Scholarship (Fall 2026 Cycle) | programme_details.json |
| 480 | LIVE | Harvard College Need-Based Financial Aid 2027-2028 | programme_details.json |
| 481 | LIVE | Yale College Need-Based Financial Aid 2027-2028 | programme_details.json |
| 482 | LIVE | MIT Undergraduate Financial Aid for International Students 2026-2027 | programme_details.json |
| 483 | LIVE | UT Austin International Student Scholarships (Spring 2027 and Fall 2027) | programme_details.json |
| 484 | LIVE | University of Chicago International Scholarships for Undergraduates | programme_details.json |
| 488 | LIVE | JWU Global Full Tuition Scholarship | programme_details.json |
| 494 | LIVE | _(untitled — check by host)_ | programme_details.json |
| 498 | LIVE | _(untitled — check by host)_ | programme_details.json |
| 508 | LIVE | _(untitled — check by host)_ | programme_details.json |
| 517 | LIVE | _(untitled — check by host)_ | programme_details.json |
| 522 | LIVE | _(untitled — check by host)_ | programme_details.json |
| 524 | LIVE | Call for applications - NAWA | programme_details.json |
| 533 | LIVE | Grundförderung für Ausländer:innen | programme_details.json |
| 605 | LIVE | ANU Vice-Chancellor's International Achievement Award | programme_details.json |
| 612 | LIVE | University of Glasgow - Sanctuary Scholarship (refugee and asylum seeker students) | programme_details.json |
| - | PENDING_INSERT | Boren Awards (Boren Scholarships and Boren Fellowships) | new_scholarships.json |
| - | PENDING_INSERT | UBC International Scholars Program | new_scholarships.json |
| - | PENDING_INSERT | Hanns-Seidel-Stiftung Scholarship – Förderung internationaler Studierender und Promovierender (Scholarship for Studies / PhDs for international students and doctoral candidates) | new_scholarships.json |
| - | PENDING_INSERT | Deutschlandstipendium | new_scholarships.json |
| - | PENDING_INSERT | Flanders Trainee Programme (Flanders Traineeship Programme) | new_scholarships.json |
| - | PENDING_INSERT | Estonian Scholarship Programme for international students, researchers and academic staff — Scholarship for degree and exchange study in Estonia | new_scholarships.json |
| - | PENDING_INSERT | Vice-Chancellor's International High Achievers Scholarship (VCIHAS) | new_scholarships.json |
| - | PENDING_INSERT | ANU Vice-Chancellor's International Achievement Award | new_scholarships.json |
| - | PENDING_INSERT | GKS (Global Korea Scholarship) Program - Undergraduate Degree Programs | new_scholarships.json |
| - | PENDING_INSERT | KAIST Scholarship (KAIST International Undergraduate Admission) | new_scholarships.json |
| - | PENDING_INSERT | UNHCR Tertiary Refugee Scholarship Programme (DAFI) - Albert Einstein German Academic Refugee Initiative | new_scholarships.json |
| - | PENDING_INSERT | University of Glasgow Sanctuary Scholarship | new_scholarships.json |
| - | PENDING_INSERT | Mastercard Foundation Scholars Program | new_scholarships.json |
| - | PENDING_INSERT | The Inlaks Fellowship for Social Engagement | new_scholarships.json |
| - | PENDING_INSERT | RISE Germany - Research Internships in Science and Engineering | new_scholarships.json |
| - | PENDING_INSERT | GrundfÃ¶rderung fÃ¼r AuslÃ¤nder:innen | new_scholarships.json |
| - | PENDING_INSERT | Scholarships for Refugees (Studien- und PromotionsfÃ¶rderung) | new_scholarships.json |
| - | PENDING_INSERT | Convocatoria de Becas OEA - UNIR, EP NEWMAN y UNIR Mexico (Curso Academico 2026, 2a convocatoria) | new_scholarships.json |
| - | PENDING_INSERT | MOFA Scholarship Program | new_scholarships.json |
| - | PENDING_INSERT | NL Scholarship (formerly Holland Scholarship) | new_scholarships.json |

## Logo override hosts already taken (357)

Do **not** add a second entry for any of these hosts:

```
a-star.edu.sg
a2ascholarships.iccr.gov.in
aai-salzburg.at
aalto.fi
aauw.org
abo.fi
adelaide.edu.au
admission.brown.edu
admission.kaist.ac.kr
admission.princeton.edu
admissions.dartmouth.edu
admissions.miami.edu
admissions.msu.edu
admissions.rochester.edu
admissions.smu.edu.sg
admissions.uiowa.edu
aecid.es
aefe.gouv.fr
akf.org
american.edu
anr.fr
apply.nthu.edu.tw
auckland.ac.nz
bandi.unibo.it
bc.edu
bd.china-embassy.gov.cn
berea.edu
bi.no
bme.hu
boell.de
borenawards.org
brandeis.edu
bse.eu
cambridgetrust.org
campusfrance.org
careers.cern
careers.univie.ac.at
cbs.dk
ccpit.org
cemm.at
cern.ch
ceu.edu
chalmers.se
chevening.org
cis.chinese.cn
clarku.edu
clinical-linguistics.eu
cmu.edu
col.org
college.harvard.edu
cranfield.ac.uk
cscuk.fcdo.gov.uk
cuhk.edu.hk
cuni.cz
cvut.cz
czs.muni.cz
daad-bangladesh.org
daad.de
dcu.ie
deakin.edu.au
deutschlandstipendium.de
dfat.gov.au
diasporascholarship.hu
documents.manchester.ac.uk
dtu.dk
dzs.cz
eacea.ec.europa.eu
eastwestcenter.org
ecowas.int
ed.ac.uk
educanada.ca
education.govt.nz
education.ki.se
educationusa.state.gov
en.aau.dk
en.mofa.gov.tw
en.snu.ac.kr
en.tka.hu
en.unito.it
english.moe.gov.tw
english.ucas.ac.cn
ens-lyon.fr
ensie.nankai.edu.cn
epfl.ch
erasmus-plus.ec.europa.eu
ethz.ch
eu.nl
exchanges.state.gov
fct.pt
fer.unizg.hr
fes.de
flinders.edu.au
foundation.scg.ch
frq.gouv.qc.ca
fulbright.fi
future.mcmaster.ca
future.utoronto.ca
futurestudents.yorku.ca
fwf.ac.at
gatescambridge.org
gilmanscholarship.org
gist.ac.kr
giz.de
global.utexas.edu
gocfs.ntu.edu.tw
gov.uk
graduate.yonsei.ac.kr
grants.oead.at
grips.ac.jp
hanken.fi
harno.ee
hea.ie
hec.edu
hec.gov.pk
hi.is
hkust.edu.hk
hss.de
humboldt-foundation.de
humphreyfellowship.org
huygens.knaw.nl
icar.gov.in
icssr.org
ie.edu
iie.org
iitk.ac.in
imd.org
imperial.ac.uk
inde.campusfrance.org
inlaksfoundation.org
inlife.sorbonne-universite.fr
insaindia.res.in
insead.edu
institut-pascal.universite-paris-saclay.fr
instituto-camoes.pt
international.au.dk
international.join-tsinghua.edu.cn
international.kiit.ac.in
international.vluhr.be
investyourtalentapplication.esteri.it
ir.iith.ac.in
ireland.ie
isd.pku.edu.cn
isdb.org
iso.fudan.edu.cn
isss.uoregon.edu
iuj.ac.jp
jasso.go.jp
jeffersonscholars.org
jku.at
jsps.go.jp
jwu.edu
kas.de
kitlv.nl
kmsp.wisc.edu
knight-hennessy.stanford.edu
knust.edu.gh
koica.go.kr
kth.se
ktu.lt
ku.dk
ku.edu.kw
ku.leuven.be
kuleuven.be
kyushu-u.ac.jp
latrobe.edu.au
liu.se
lse.ac.uk
lu.lv
lunduniversity.lu.se
maastrichtuniversity.nl
manchester.ac.uk
mandelarhodes.org
marie-sklodowska-curie-actions.ec.europa.eu
marihe.eu
master-ediss.eu
masters.au.dk
mau.se
mccallmacbainscholars.org
mext.go.jp
mha.gov.sg
mindef.gov.sg
mo.ibrahim.foundation
modul.ac.at
moe.gov.cn
moe.gov.sg
mofa.gov.ae
momentummsca.mta.hu
monash.edu
mq.edu.au
msmt.gov.cz
nawa.gov.pl
nias.knaw.nl
nokiafoundation.com
novasbe.unl.pt
nsf.gov
ntnu.edu
ntu.edu.sg
nus.edu.sg
nusgs.nus.edu.sg
oas.org
oead.at
oia-scholarship.nycu.edu.tw
oia.ncku.edu.tw
oia.ntu.edu.tw
oia.nycu.edu.tw
otago.ac.nz
oulu.fi
pasteur.fr
phd.ista.ac.at
phikappaphi.org
polimi.it
polyu.edu.hk
portalvs.sk
postf.org
psc.gov.sg
research.google
research.ie
researchireland.ie
rhodeshouse.ox.ac.uk
rmit.edu.au
rotary-yoneyama.or.jp
rotary.org
royalsociety.org
royalsociety.org.nz
ru.ac.za
ru.nl
rug.nl
sbfi.admin.ch
scholarships.online.unsw.edu.au
scholarships.unimelb.edu.au
scholarships.uq.edu.au
science.osti.gov
sciencespo.fr
sdu.dk
semmelweis.hu
semmelwis.hu
seu.ub.edu
sfs.mit.edu
sfu.ca
sgs.utoronto.ca
sharjah.ac.ae
si.se
simmons.edu
snf.ch
soka.ac.jp
southafrica-france-scholarships.com
sshrc-crsh.canada.ca
stipendien.oeaw.ac.at
stipendiumhungaricum.hu
student.universiteitleiden.nl
studentaid.alberta.ca
studienfinanzierung.uzh.ch
studieren.univie.ac.at
studies.ku.dk
study-uk.britishcouncil.org
study.anu.edu.au
study.fsv.cuni.cz
studyinaustria.at
studyinbelgium.be
studyindenmark.dk
studyinfinland.fi
studyinhungary.hu
studyinindia.gov.in
studyinitaly.esteri.it
studyinjapan.go.jp
studyinkorea.go.kr
studyinlatvia.lv
studyinnl.org
studyinnorway.no
studyinpoland.pl
stypendia.uj.edu.pl
su.se
suss.edu.sg
sutd.edu.sg
swissuniversities.ch
sydney.edu.au
taiwanscholarship.moe.gov.tw
taltech.ee
tampere.fi
tcd.ie
tigp.sinica.edu.tw
tilburguniversity.edu
tlu.ee
tonyelumelufoundation.org
trudeaufoundation.ca
tudelft.nl
tuni.fi
tuwien.at
twas.org
ucd.ie
uchicago.edu
ucl.ac.uk
uct.ac.za
uef.fi
ufh.ac.za
ug.edu.gh
ugc.gov.in
ugent.be
uhr.no
uibk.ac.at
uic.yonsei.ac.kr
um.edu.mt
um.si
umu.se
un.org
unesco.org
uni-graz.at
uni-lj.si
uni.li
unibas.ch
unibo.it
unibs.it
unicam.it
unil.ch
unimelb.edu.au
unimib.it
unipd.it
uniroma1.it
unisg.ch
universitaly.it
universite-paris-saclay.fr
universiteitleiden.nl
universitiesnz.ac.nz
universityofgalway.ie
unizg.hr
up.pt
ur.ac.rw
us.fulbrightonline.org
ust.hk
ut.ee
utoronto.ca
uts.edu.au
utu.fi
utwente.nl
uu.nl
uu.se
uva.nl
uwa.edu.au
uwaterloo.ca
vgtu.lt
visegradfund.org
vsb.cz
vu.nl
wa.gov.au
waikato.ac.nz
wbi.be
webster.ac.at
wgtn.ac.nz
wipo.int
wits.ac.za
workforce.education.govt.nz
worldbank.org
wur.nl
www2.daad.de
yorku.ca
you.ubc.ca
youarewelcomehereusa.org
```
