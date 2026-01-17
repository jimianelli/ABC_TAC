library(here)
library(patchwork)
library(scales)
library(tidyverse)
library(viridis)           # Load
library(wesanderson)
#pak::pkg_install("Sebastien-Le/YesSiR")
library(YesSiR) # to export a flextable into MS Excel: exportxlsx() function
df <- read_csv(here("data","BSAI_OFL_ABC_TAC.csv"))
names(df)
glimpse(df)
# Test that OY sum of TACs is correct
df %>% filter(lag==1,OY==1) %>% group_by(Year=ProjYear) %>% summarise(sum(TAC,na.rm=TRUE)) %>% print(n=Inf)
df %>% filter(lag==2,OY==1) %>% group_by(Year=ProjYear) %>% summarise(sum(TAC,na.rm=TRUE)) %>% print(n=Inf)
df


dfOY <-df %>% filter(OY==1) %>%
       group_by(Year=ProjYear,lag,Species,Order) %>%
summarise(ABC=sum(ABC,na.rm=TRUE), OFL=sum(OFL,na.rm=TRUE), TAC=sum(TAC,na.rm=TRUE))
glimpse(dfOY)

dfOY %>% filter(lag==1,Year==2002) %>% print(n=Inf)#%>% group_by(Year) %>% summarise(sum(ABC),sum(TAC)-2e6) %>%print(n=Inf)
dfOY %>% filter(lag==1) %>% group_by(Year) %>% summarise(sum(ABC),sum(TAC)-2e6) %>%print(n=Inf)
# Greater than 90% of TAC and ABC
mainspp<- c("Pollock","Yellowfin sole","Pacific cod","Atka mackerel","Northern rock sole","Flathead sole","Pacific ocean perch")
mainspp[2]
# Ratio of ABC sum / 2mmt
df %>% filter(lag==1,OY==1,Species %in% mainspp) %>% group_by(Year=ProjYear) %>% summarise(sum(ABC,na.rm=TRUE)/2000000) %>% print(n=Inf)

dfOY
# Table of means and cvsAll years
df %>% filter(lag==1,OY==1,Species %in% mainspp[7]) %>% summarise(sd(ABC,na.rm=TRUE)/mean(ABC,na.rm=TRUE)) #print(n=Inf)#%>% group_by(Year=ProjYear,Species) %>%
ft<-df %>% filter(lag==1,OY==1,Species %in% mainspp) %>% group_by(Year=ProjYear,Species) %>%
mutate(ABC=sum(ABC,na.rm=TRUE), OFL=sum(OFL,na.rm=TRUE), TAC=sum(TAC,na.rm=TRUE)) %>%
ungroup()%>%
       group_by(Species) %>% summarise(
        mn_ABC=mean(ABC,na.rm=T), sd_ABC=sd(ABC,na.rm=T), cv_ABC=sd(ABC,na.rm=TRUE)/mean(ABC,na.rm=TRUE),
        mn_TAC=mean(TAC,na.rm=T), sd_TAC=sd(TAC,na.rm=T), cv_TAC=sd_TAC/mn_TAC,
        mn_OFL=mean(OFL,na.rm=T), sd_OFL=sd(OFL,na.rm=T), cv_OFL=sd_OFL/mn_OFL
      ) #%>% flextable::flextable()
ft %>% select(Species,ABC=cv_ABC,TAC=cv_TAC)
exportxlsx(ft, path = "sum.xlsx");system("open sum.xlsx")

#Recent years
mainspp
ftround<-df %>% filter(ProjYear>2001,OY==1,Species %in% mainspp[c(1,3,4)]) %>%
       group_by(Year=ProjYear,Species,lag) %>%
mutate(ABC=sum(ABC,na.rm=TRUE), OFL=sum(OFL,na.rm=TRUE), TAC=sum(TAC,na.rm=TRUE)) %>%
       group_by(Species,lag) %>% summarise(
        mn_ABC=mean(ABC,na.rm=T), sd_ABC=sd(ABC,na.rm=T), cv_ABC=sd_ABC/mn_ABC,
        mn_TAC=mean(TAC,na.rm=T), sd_TAC=sd(TAC,na.rm=T), cv_TAC=sd_TAC/mn_TAC,
        mn_OFL=mean(OFL,na.rm=T), sd_OFL=sd(OFL,na.rm=T), cv_OFL=sd_OFL/mn_OFL
      )%>%ungroup() #%>% flextable::flextable()
       ftround
ft<-df %>% filter(ProjYear>2001,OY==1,Species %in% mainspp) %>%
       group_by(Year=ProjYear,Species,lag) %>%
mutate(ABC=sum(ABC,na.rm=TRUE), OFL=sum(OFL,na.rm=TRUE), TAC=sum(TAC,na.rm=TRUE)) %>%
       group_by(Species,lag) %>% summarise(
        mn_ABC=mean(ABC,na.rm=T), sd_ABC=sd(ABC,na.rm=T), cv_ABC=sd_ABC/mn_ABC,
        mn_TAC=mean(TAC,na.rm=T), sd_TAC=sd(TAC,na.rm=T), cv_TAC=sd_TAC/mn_TAC,
        mn_OFL=mean(OFL,na.rm=T), sd_OFL=sd(OFL,na.rm=T), cv_OFL=sd_OFL/mn_OFL
      ) #%>% flextable::flextable()
       ft

ftround %>% filter(lag==1) %>% select(Species,ABC=cv_ABC,TAC=cv_TAC) %>%
         pivot_longer(cols=2:3,names_to="Measure",values_to="CV") %>%
         ggplot(aes(x=Species,y=CV,fill=Measure,color=Measure,shape=Measure)) + ggthemes::theme_few(base_size=12)+
          geom_bar(stat='identity',position='dodge')
          geom_point(size=3)

exportxlsx(ft, path = "sum.xlsx");system("open sum.xlsx")

df %>% filter((AssmentYr-ProjYear)==-1) %>%
       filter(Area %in% c("BS","EBS"), Species %in% c("Pollock")) %>%
       pivot_longer( cols=6:8, names_to="Measure" ) %>% select(Year=ProjYear,Measure,value) %>%
       ggplot(aes(y=value/1000, x=Year,color=Measure)) + geom_line(linewidth=3) + ggthemes::theme_few(base_size=20) +
       scale_y_continuous(limits=c(0,4.8e3),labels=comma) + ylab("thousands of tons");p1

p1$data

# plot difference between 2-year and final for pollocks
#p1 <-
#Simple time series of the two figuresjjjjjjjjjjj

      # distinct(paste(Species,Area,ProjYear)) %>%
df %>% filter(Species=="Pollock",Area=="BS") #%>% distinct(paste(Species,Area))

p1 <-dfOY %>% filter(Year>1991,lag==1) %>%
       filter(Species %in% c("Pollock")) %>%
       pivot_longer( cols=c(7,5), names_to="Measure" ) %>% select(Year=Year,Measure,value) %>%
       ggplot(aes(y=value/1000, x=Year,color=Measure)) + geom_line(linewidth=2) + ggthemes::theme_few (base_size=20) +
       scale_x_continuous(limits=c(1992,2024),breaks=seq(1992,2025,by=3)) +
       scale_y_continuous(limits=c(0,3.0e3),labels=comma) + ylab("thousands of tons");p1

p1$data
# plot difference between 2-year and final for pollocks
tail(dat)
dat <-dfOY %>% filter(Species %in% mainspp) %>% mutate(Stock= fct_reorder(Species, -Order),
  Species= fct_reorder(Species, Order),
                    lag=ifelse(lag==2,"two","one")) %>%
    select(Stock,Species,Year,TAC,ABC,lag,Order) |> pivot_wider(names_from=lag,values_from=c(TAC,ABC)) %>%
    mutate(
      ABC_deltat=(ABC_one-ABC_two)/1000,
      TAC_deltat=(TAC_one-TAC_two)/1000,
      ABC_delta =(ABC_one-ABC_two)/ABC_two,
      TAC_delta =(TAC_one-TAC_two)/ABC_two,
      TAC_sign  =ifelse(TAC_delta<0,"-","+"),
      ABC_sign  =ifelse(ABC_delta<0,"-","+")
    )
glimpse(dat)
#library(RColorBrewer)
#cbp1 <- c("#999999", "#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00", "#CC79A7")

#do bars
dftmp<-dat |> filter(Year>1990) %>% arrange(Stock,Year)
#filter(!Stock %in% c("Other species","Squids",
      #"Blackspotted/Rougheye Rockfish","Greenland turbot","Alaska plaice",
      #"Octopuses","Kamchatka flounder", "Skates","Sharks","Sculpins"),
      #Area %in% c("BSAI","EBS") ) %>%

glimpse(dftmp)
#TAC %
p0<-ggplot(dftmp,aes(x=Year,y=TAC_delta,fill=TAC_delta) ) + geom_bar(stat='identity') +
      labs(fill="Change in \n TAC (%)",y="Change from 2-year projection to final") +
      scale_y_continuous(labels=percent) +
      geom_smooth(se=F,color="brown") +
      facet_grid(fct_reorder(Species,Order)~.,scales="free") +
      geom_hline(color="grey70",yintercept=0,linewidth=0.5,linetype=1) +
    ggthemes::theme_few() + theme(strip.text.y.right = element_text(angle = 0)) +
    scale_fill_gradient2( low = muted("red"), mid = "white", high = muted("blue"),
    na.value = "grey90", midpoint = 0 ); p0
dftmp[,c(1,3,12)] |> print(n=Inf)

#TAC kt
p0<-ggplot(dftmp,aes(x=Year,y=TAC_deltat,fill=TAC_deltat) ) + geom_bar(stat='identity') +
      labs(fill="Change in \n TAC (kt)",y="Change from 2-year projection to final") +
      scale_y_continuous(labels=comma) +
      geom_smooth(se=F,color="brown") +
      facet_grid(fct_reorder(Species,Order)~.,scales="free") +
      geom_hline(color="grey70",yintercept=0,linewidth=0.5,linetype=1) +
    ggthemes::theme_few() + theme(strip.text.y.right = element_text(angle = 0)) +
    scale_fill_gradient2( low = muted("red"), mid = "white", high = muted("blue"),
    na.value = "grey90", midpoint = 0 ); p0

#TAC kt w/o pollock
p0<-ggplot(dftmp%>%filter(Species!="Pollock"),aes(x=Year,y=TAC_deltat,fill=TAC_deltat) ) + geom_bar(stat='identity') +
      labs(fill="Change in \n TAC (kt)",y="Change from 2-year projection to final") +
      scale_y_continuous(labels=comma) +
      geom_smooth(se=F,color="brown") +
      facet_grid(fct_reorder(Species,Order)~.,scales="free") +
      geom_hline(color="grey70",yintercept=0,linewidth=0.5,linetype=1) +
    ggthemes::theme_few() + theme(strip.text.y.right = element_text(angle = 0)) +
    scale_fill_gradient2( low = muted("red"), mid = "white", high = muted("blue"),
    na.value = "grey90", midpoint = 0 ); p0

#ABC
p0<-ggplot(dftmp,aes(x=Year,y=ABC_deltat,fill=ABC_deltat) ) + geom_bar(stat='identity') +
      labs(fill="Change in \n ABC (kt)",y="Change from 2-year projection to final") +
      scale_y_continuous(labels=comma) +
      geom_smooth(se=F,color="brown") +
      facet_grid(fct_reorder(Species,Order)~.,scales="free") +
      geom_hline(color="grey70",yintercept=0,linewidth=0.5,linetype=1) +
    ggthemes::theme_few() + theme(strip.text.y.right = element_text(angle = 0)) +
    scale_fill_gradient2( low = muted("red"), mid = "white", high = muted("blue"),
    na.value = "grey90", midpoint = 0 ); p0

p1<-ggplot(dftmp,aes(x=Year,y=ABC_deltat/1e3,fill=ABC_deltat/1e3) ) + geom_bar(stat='identity') +
      labs(y="Change from 2-year ojection to final (kt) ",fill="Change in \n ABC (kt)") + facet_grid(Stock~.) +
        geom_hline(color="grey70",yintercept=0,linewidth=0.5,linetype=1) +
    ggthemes::theme_few() + theme(strip.text.y.right = element_text(angle = 0)) +
    scale_fill_gradient2( low = muted("red"), mid = "white", high = muted("blue"),
    na.value = "grey90", midpoint = 0 ); p1
#ABC w/o pollock
p2<-ggplot(dftmp%>%filter(Stock!="Pollock"),aes(x=Year,y=ABC_deltat/1e3,fill=ABC_deltat/1e3) ) + geom_bar(stat='identity') +
      labs(y="Change from 2-year projection to final (kt) ",fill="Change in \n ABC (kt)") + facet_grid(Stock~.) +
        geom_hline(color="grey70",yintercept=0,linewidth=0.5,linetype=1) +
    ggthemes::theme_few() + theme(strip.text.y.right = element_text(angle = 0)) +
    scale_fill_gradient2( low = muted("red"), mid = "white", high = muted("blue"),
    na.value = "grey90", midpoint = 0 ); p2
    p0|p1|p2

#Do tiles
dftmp

p0<-ggplot(dftmp,aes(x=Year,y=fct_reorder(Species,-Order) ,fill=ABC_delta) ) + geom_tile() +
      labs(fill="Change in \n ABC (%)",y="Stock") + scale_fill_gradient2( low = muted("red"), mid = "white", high = muted("blue"), na.value = "grey90", midpoint = 0 ); p0
p1<-ggplot(dftmp,aes(x=Year,y=fct_reorder(Species,-Order) ,fill=ABC_deltat) ) + geom_tile() +
      labs(fill="Change in \n ABC (kt)",y="Stock") + scale_fill_gradient2( low = muted("red"), mid = "white", high = muted("blue"), na.value = "grey90", midpoint = 0 ); p1
p2<-ggplot(dftmp%>%filter(Species!="Pollock"),aes(x=Year,y=fct_reorder(Species,-Order) ,fill=ABC_deltat) ) + geom_tile() +
      labs(fill="Change in \n ABC (kt)",y="Stock") + scale_fill_gradient2( low = muted("red"), mid = "white", high = muted("blue"), na.value = "grey90", midpoint = 0 ); p2
    p0/p1/p2

p0<-ggplot(dftmp,aes(x=Year,y=fct_reorder(Species,-Order) ,fill=TAC_delta) ) + geom_tile() +
      labs(fill="Change in \n TAC (%)",y="Stock") + scale_fill_gradient2( low = muted("red"), mid = "white", high = muted("blue"), na.value = "grey90", midpoint = 0 ); p0
p1<-ggplot(dftmp,aes(x=Year,y=fct_reorder(Species,-Order) ,fill=TAC_deltat) ) + geom_tile() +
      labs(fill="Change in \n TAC (kt)",y="Stock") + scale_fill_gradient2( low = muted("red"), mid = "white", high = muted("blue"), na.value = "grey90", midpoint = 0 ); p1
p2<-ggplot(dftmp%>%filter(Species!="Pollock"),aes(x=Year,y=fct_reorder(Species,-Order) ,fill=TAC_deltat) ) + geom_tile() +
      labs(fill="Change in \n TAC (kt)",y="Stock") + scale_fill_gradient2( low = muted("red"), mid = "white", high = muted("blue"), na.value = "grey90", midpoint = 0 ); p2
    p0/p1/p2

    p1 <- p1 + ggtitle(title)
    if (Year!="Year")
      p1 <- p1 + geom_smooth() + geom_text(aes(label=substring(as.character(Year),3,4)))+
                 xlab(paste("Final",colplot,"(t)"))+
                 scale_x_continuous(labels=comma) + geom_path(linetype=3,linewidth=0.5)
    else
      p1 <- p1 + geom_bar(
        stat='identity')
    if (colplot=="ABC")
      p1 <- p1 + ylab(expression(ABC~Delta))
    else
      p1 <- p1 + ylab(expression(TAC~Delta))
    return(p1)
  }

plot_ch <- function(dat=dat,xaxis="Year",title="Pollock",area="EBS",colplot="ABC",showtitle=TRUE,yl=c(-.2,.2)){
    ymean=dat %>% ungroup()%>%filter(Species==title) %>% summarise(ymean=mean(get(paste0(colplot,"_delta")),na.rm=TRUE ))
    p1<-ggplot(dat%>%filter(Species==title),
      aes_string(x=xaxis,y=paste0(colplot,"_delta"),
      fill=paste0(colplot,"_sign") )) +
    scale_y_continuous(labels=percent,limits=yl) + ggthemes::theme_few()
    if (showtitle)
    p1 <- p1 + ggtitle(title)
    if (xaxis!="Year")
      p1 <- p1 + geom_smooth(fill="salmon",se=FALSE) +
         geom_text(aes(label=substring(as.character(Year),3,4)))+
                 xlab(paste("Final",colplot,"(t)"))+
                 scale_x_continuous(labels=comma) + geom_path(linetype=3,linewidth=0.5)
    else
    {
      p1 <- p1 + geom_bar( stat='identity')
      p1 <- p1 + geom_hline(color="grey70",yintercept=0,linewidth=0.5,linetype=1) #+
      p1 <- p1 + geom_hline(color="grey30",yintercept=ymean$ymean,linewidth=0.5,linetype=2)
      p1 <- p1 + geom_text(aes( x=2005, y=ymean$ymean*2,
             label=paste0(100*round(ymean$ymean,2),"%") ) )
           #color="orange", size=7 , angle=45, fontface="bold" )
    }
    if (colplot=="ABC")
      p1 <- p1 + ylab(expression(ABC~Delta))
    else
      p1 <- p1 + ylab(expression(TAC~Delta))
    return(p1)
  }
  p1
  dat %>% filter(Species=="Pollock",Year>2001)
  names(dat)

  yl=c(-.45,.45)
  for (spp in mainspp){
  plot_ch(dat=dat,xaxis="Year",title=spp,colplot="ABC",yl=yl) /
  plot_ch(dat=dat,xaxis="Year",title=spp,colplot="TAC",yl=yl,showtitle=FALSE)
ggsave(paste0("figs/sqproj_",spp,".png"))
  }

  plot_ch(dat=dat,xaxis="ABC_one",title="Pollock",colplot="ABC",yl=c(-.45,.42) ) /
  plot_ch(dat=dat,xaxis="ABC_one",title="Pollock",colplot="TAC",yl=c(-.45,.42), showtitle=FALSE)


  yl=c(-1.5,1.5)
  plot_ch(dat=dat,xaxis="Year",title="Yellowfin sole",colplot="ABC",yl=yl) /
  plot_ch(dat=dat,xaxis="Year",title="Yellowfin sole",colplot="TAC",yl=yl,showtitle=FALSE)

  yl=c(-.3,.3)
  plot_ch(dat=dat,xaxis="Year",title="Pacific cod",colplot="ABC",yl=yl) /
  plot_ch(dat=dat,xaxis="Year",title="Pacific cod",colplot="TAC",yl=yl,showtitle=FALSE)

  yl=c(-0.8,0.8)
  plot_ch(dat=dat,xaxis="Year",title="Atka mackerel",colplot="ABC",yl=yl) /
  plot_ch(dat=dat,xaxis="Year",title="Atka mackerel",colplot="TAC",yl=yl,showtitle=FALSE)

  plot_ch(dat=dat,xaxis="Year",title="Northern rock sole",colplot="ABC",yl=yl) /
  plot_ch(dat=dat,xaxis="Year",title="Northern rock sole",colplot="TAC",yl=yl,showtitle=FALSE)

  # Create a fake scenario where the two year out was the same as the prvious 1-year out
  # to test if rollovers outperform
#d,fro <-
  #Pollock

# Now plot diffs of spoofed next year ABC/TACs
for (spp in mainspp) {
dfABC<-dfOY %>% ungroup()%>%filter(Year>2000,Species %in% spp ) %>%
mutate(lag=ifelse(lag==1,"Used","Projected") ) %>% select(Year,ABC,application=lag) ;

dfTAC<-dfOY %>% ungroup()%>%filter(Year>2000,Species %in% spp ) %>%
mutate(lag=ifelse(lag==1,"Used","Projected") ) %>% select(Year,TAC,application=lag) ;

  dtmp<-dfABC %>% pivot_wider(names_from="application",values_from="ABC")%>%
mutate(Projected=lag(Used,order_by=Year),
      ABC_deltat=(Used-Projected)/1000,
      ABC_delta =(Used-Projected)/Projected,
      sign=ifelse(ABC_delta<0,"-","+")
)
p1<-dtmp%>%    ggplot( aes(x=Year,y=ABC_delta , fill=sign ))  +
      geom_bar( stat='identity')  +
      labs(fill="Change in \n ABC (%)",y=expression(ABC~Delta)) +
      geom_hline(color="grey70",yintercept=0,linewidth=0.5,linetype=1) +
      geom_hline(color="grey30",yintercept=ymean$ymean,linewidth=0.5,linetype=2) +
    scale_y_continuous(labels=percent,limits=yl) + ggthemes::theme_few()
ymeanABC<-   p1$data%>%     summarise(ymean=mean(ABC_delta,na.rm=TRUE ))
p1 <- p1+ geom_text(aes( x=2005, y=ymeanABC$ymean*2,
        label=paste0(100*round(ymeanABC$ymean,2),"%") ) )  + ggtitle("Rollover");p1

# FOR TAC
dtmp<-dfTAC %>% pivot_wider(names_from="application",values_from="TAC")%>%
mutate(Projected=lag(Used,order_by=Year),
      TAC_deltat=(Used-Projected)/1000,
      TAC_delta =(Used-Projected)/Projected ,
      sign=ifelse(TAC_delta<0,"-","+")
)
p2<-dtmp%>%    ggplot( aes(x=Year,y=TAC_delta , fill=sign ))  +
      geom_bar( stat='identity')  +
      labs(fill="Change in \n TAC (%)",y=expression(TAC~Delta)) +
      geom_hline(color="grey70",yintercept=0,linewidth=0.5,linetype=1) +
      geom_hline(color="grey30",yintercept=ymean$ymean,linewidth=0.5,linetype=2) +
    scale_y_continuous(labels=percent,limits=yl) + ggthemes::theme_few()
ymean<-   p2$data%>%     summarise(ymean=mean(TAC_delta,na.rm=TRUE ))
p2 <- p2+ geom_text(aes( x=2005, y=ymean$ymean*2,
        label=paste0(100*round(ymean$ymean,2),"%") ) ) + ggtitle(spp) ;p2
p1/p2
ggsave(paste0("figs/rollover_",spp,".png"))
}


dat%>%ungroup()%>%filter(Year>2000) %>% mutate(TAC_two = lag(TAC_one, order_by = Year))%>%
arrange(Year) %>%print(n=1000)


#Simple time series of the two figuresjjjjjjjjjjj
for (spp in mainspp) {
dftmp<-dfOY %>% filter(Year>2004,Species %in% spp ) %>%
mutate(lag=ifelse(lag==1,"Used","Projected") ) %>% select(Year,ABC,lag) ;

p0<-dftmp%>%
ggplot(aes(x=Year,y=ABC/1000,color=lag)) + expand_limits(y=0)+
  scale_y_continuous(labels=comma) + ylab("thousands of tons") +
  ggthemes::theme_few() + geom_line(size=1.4) + geom_point(size=2)
tail(dftmp)

dfro <- dftmp%>%pivot_wider(names_from="lag",values_from="ABC")%>%
ungroup()%>% mutate(Projected=lag(Used,order_by=Year)) %>%
        pivot_longer(cols=3:4,names_to="lag",values_to="ABC")

dfro
p1<- dfro %>%
ggplot(aes(x=Year,y=ABC/1000,color=lag)) + ggtitle(spp) + expand_limits(y=0)+
  scale_y_continuous(labels=comma) + ylab("thousands of tons") +
  ggthemes::theme_few() + geom_line(size=1.4) + geom_point(size=2);p1
p0/p1
ggsave(paste0("figs/ts_",spp,".png"))
p0/p1
}

dfro
dat <-dfro %>%
    select(Species,Year,TAC,A/BC,lag,Order) |> pivot_wider(names_from=lag,values_from=c(TAC,ABC)) %>%
    mutate(
      ABC_deltat=(ABC_one-ABC_two)/1000,
      TAC_deltat=(TAC_one-TAC_two)/1000,
      ABC_delta =(ABC_one-ABC_two)/ABC_two,
      TAC_delta =(TAC_one-TAC_two)/ABC_two,
      TAC_sign  =ifelse(TAC_delta<0,"-","+"),
      ABC_sign  =ifelse(ABC_delta<0,"-","+")
    )
tail(dat)
#library(RColorBrewer)
#cbp1 <- c("#999999", "#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00", "#CC79A7")

    if (showtitle)
    p1 <- p1 + ggtitle(title)
    if (xaxis!="Year")
      p1 <- p1 + geom_smooth(fill="salmon",se=FALSE) +
         geom_text(aes(label=substring(as.character(Year),3,4)))+
                 xlab(paste("Final",colplot,"(t)"))+
                 scale_x_continuous(labels=comma) + geom_path(linetype=3,linewidth=0.5)
    else
    {
           #color="orange", size=7 , angle=45, fontface="bold" )
    }
