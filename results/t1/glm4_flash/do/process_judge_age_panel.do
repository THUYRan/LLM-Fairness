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
	global path_base="C:/Users/86158/Desktop/标签检测"
}
else {
    display "Your operating system is not identified"
}


global filename = "merged_judge_age_glm4_flash"
*global keyword="法律援助律师"

cap log close
cap log using "$path_base/log/${filename}_${date}.log", append
cap set processors 2
cap set processors 4
cap set processors 8

import excel "$path_base/merged/$filename.xlsx", sheet("Sheet1") firstrow clear

gen defendant_age_llm=label_value
destring defendant_age_llm,force replace
gen lgage_llm=log(defendant_age_llm)

gen treated=0
*replace treated=1 if label_value=="$keyword"
replace treated=lgage_llm

destring llm_刑期, replace 
gen lgxq_llm=log(llm_刑期+1)
gen llm_刑期_full=llm_刑期
gen fajin=0
replace fajin = 1 if strpos(llm_刑罚类型, "罚金") > 0
replace llm_刑期_full=300 if llm_刑罚类型=="无期徒刑"
replace llm_刑期_full=400 if llm_刑罚类型=="死刑缓期执行"
replace llm_刑期_full=600 if llm_刑罚类型=="死刑立即执行"
replace llm_刑期_full=600 if llm_刑罚类型=="死刑" //折算方式 参考白建军：量刑基准实证研究（[1]白建军.(2008).量刑基准实证研究. 法学研究(01),97-105. doi:CNKI:SUN:LAWS.0.2008-01-011.）
replace llm_刑期_full=0 if fajin==1
replace llm_刑期_full=llm_刑期/2 if llm_刑罚类型=="管制" //拘役一天算一天，不用改，管制一天算半天，参考我国关于已羁押时长折抵刑期的规定
gen lgxq_llm_full=log(llm_刑期_full+1)

reg lgxq_llm treated i.ID if llm_刑罚类型=="有期徒刑" & llm_刑期<=600  ,vce(cluster ID) //*+
outreg2 using "$path_base/log/${filename}_${date}.xls", replace

set scheme white_tableau
graph set window fontface "Times New Roman"
coefplot,  keep (treated) xline(0) ylabel(1 "{bf:Judge Age}" , labsize(medium) tstyle(major_notick)) xlabel (,labsize(medium)) xtitle( "{bf:Coefficient}",size(medium))  ///
	graphregion(margin(small)) ///
	plotregion(margin(small)) ///
	text(, fontface("Times")) levels(95 90 ) ///
	saving("$path_base/figure/$filename", replace ) 	
	

graph export  "$path_base/figure/$filename.png", width(2400)  replace

//稳健性检验
reg lgxq_llm_full treated i.ID if llm_刑期<=600  ,vce(cluster ID)
outreg2 using "$path_base/log/${filename}_${date}_outcomefull.xls", replace

reg llm_刑期 treated i.ID if llm_刑罚类型=="有期徒刑" & llm_刑期<=400  ,vce(cluster ID) //*+
outreg2 using "$path_base/log/${filename}_${date}_nolog.xls", replace

//增加稳健性检验的代码
generate below2014 = 0
*使用正则表达式匹配并设置新变量
replace below2014 = 1 if regexm(案号Case_number, "200[0-9]|201[0-3]")
reg lgxq_llm treated i.ID if llm_刑罚类型=="有期徒刑" & llm_刑期<=400  & below2014==0 ,vce(cluster ID) 
outreg2 using "$path_base/log/${filename}_${date}_2014.xls", replace

reg lgxq_llm treated  i.ID if llm_刑罚类型=="有期徒刑" & llm_刑期<=400  ,vce(robust) 
outreg2 using "$path_base/log/${filename}_${date}_r.xls", replace

reg lgxq_llm treated  i.ID if llm_刑罚类型=="有期徒刑" & llm_刑期<=400  ,vce(cluster 被告人1罪名1罪名Crime_name) 
outreg2 using "$path_base/log/${filename}_${date}_crime.xls", replace


cap log close



