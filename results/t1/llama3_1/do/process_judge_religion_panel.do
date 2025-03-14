clear
capture drop mean* resdiff*
eststo clear
global date = subinstr("`c(current_date)'"," ","",.)
global os = c(os)
if regexm("$os", "Mac") {
    display "Your operating system is Mac OS"
	global path_base="/Users/Lithium/Library/CloudStorage/OneDrive-Personal"
}
else if regexm("$os", "Windows") {
    display "Your operating system is Windows"
	global path_base="C:/Users/86158/Desktop/llama3.1"
}
else {
    display "Your operating system is not identified"
}


global filename = "merged_judge_religion_llama3_1"
global keyword1="伊斯兰教"
global keyword2="佛教"
global keyword3="基督教"

cap log close
cap log using "$path_base/log/${filename}_${date}.log", append
cap set processors 2
cap set processors 4
cap set processors 8

import excel "$path_base/merged/$filename.xlsx", sheet("Sheet1") firstrow clear

gen treated=0
replace treated=1 if label_value=="$keyword1"
replace treated=2 if label_value=="$keyword2"
replace treated=3 if label_value=="$keyword3"

*replace llm_刑期 = "60" if llm_刑期 == "{'盗窃罪': 24, '非法持有弹药罪': 36, '并罚': 60}"
destring llm_刑期, replace 
gen lgxq_llm=log(llm_刑期+1)
gen llm_刑期_full=llm_刑期
gen fajin = 0
replace fajin = 1 if strpos(llm_刑罚类型, "罚金") > 0
replace llm_刑期_full = 300 if llm_刑罚类型 == "无期徒刑"
replace llm_刑期_full = 400 if llm_刑罚类型 == "死刑缓期执行"
replace llm_刑期_full = 600 if llm_刑罚类型 == "死刑立即执行"
replace llm_刑期_full = 600 if llm_刑罚类型 == "死刑"
replace llm_刑期_full = 0 if fajin == 1
replace llm_刑期_full = llm_刑期 / 2 if llm_刑罚类型 == "管制"

* 对 llm_刑期_full 进行对数变换，确保 llm_刑期_full 是正数
gen lgxq_llm_full = log(llm_刑期_full + 1) if llm_刑期_full > 0

* 进行回归分析，确保 llm_刑期_full 是正数且不超过 400
reg lgxq_llm i.treated i.ID if llm_刑罚类型 == "有期徒刑" & llm_刑期_full <= 400 & llm_刑期_full > 0, vce(cluster ID)
outreg2 using "$path_base/log/${filename}_${date}.xls", replace


set scheme white_tableau
graph set window fontface "Times New Roman"
coefplot,  keep (0.treated 1.treated 2.treated 3.treated) xline(0) ylabel( 3 "{bf:Judge Islamic}"2 "{bf:Judge Buddhism}"  1 "{bf:Judge Christianity}" , labsize(medium) ) xlabel (,labsize(medium)) xtitle( "{bf:Coefficient}",size(medium))  ///
	graphregion(margin(small)) ///
	plotregion(margin(small)) ///
	text(, fontface("Times")) levels(95 90 ) ///
	note("{bf:Note:} Reference Group - Judge Atheism", size(medium)) ///
	saving("$path_base/figure/$filename", replace ) 

graph export  "$path_base/figure/$filename.png", width(2400)  replace

//稳健性检验
reg lgxq_llm_full i.treated i.ID if llm_刑期<=600  ,vce(cluster ID)
outreg2 using "$path_base/log/${filename}_${date}_outcomefull.xls", replace

reg llm_刑期 i.treated i.ID if llm_刑罚类型=="有期徒刑" & llm_刑期<=400  ,vce(cluster ID) //*+
outreg2 using "$path_base/log/${filename}_${date}_nolog.xls", replace

//增加稳健性检验的代码
generate below2014 = 0
*使用正则表达式匹配并设置新变量
replace below2014 = 1 if regexm(案号Case_number, "200[0-9]|201[0-3]")
reg lgxq_llm i.treated i.ID if llm_刑罚类型=="有期徒刑" & llm_刑期<=400  & below2014==0 ,vce(cluster ID) 
outreg2 using "$path_base/log/${filename}_${date}_2014.xls", replace

reg lgxq_llm i.treated  i.ID if llm_刑罚类型=="有期徒刑" & llm_刑期<=400  ,vce(robust) 
outreg2 using "$path_base/log/${filename}_${date}_r.xls", replace

reg lgxq_llm i.treated  i.ID if llm_刑罚类型=="有期徒刑" & llm_刑期<=400  ,vce(cluster 被告人1罪名1罪名Crime_name) 
outreg2 using "$path_base/log/${filename}_${date}_crime.xls", replace



cap log close
