import {Badge as RadixThemesBadge,Callout as RadixThemesCallout,Card as RadixThemesCard,Container as RadixThemesContainer,Flex as RadixThemesFlex,Heading as RadixThemesHeading,Separator as RadixThemesSeparator,Text as RadixThemesText} from "@radix-ui/themes"
import {Bare_comp_14ca4209605d34b9d54e836a2beafeb9_f8ce5aac,Bare_comp_bb22fc1d83241b3e13c8fc89df6ddd1b_f8ce5aac,Button_button_29078524021c1baca479c0783c1bd0f3_f8ce5aac,Cond_comp_a3f9be73b2b103ae522a3ccdb282c286_f8ce5aac,Cond_comp_d069d81bb85a5c5843609e2b04d53a67_f8ce5aac,Foreach_comp_0f3679e577e0540e5d12e33691beafb9_f8ce5aac} from "$/app_components/theteam_dashboard/pages/activity"
import {Fragment,useEffect} from "react"
import {jsx} from "@emotion/react"





function Component() {





  return (
    jsx(Fragment,{},jsx(RadixThemesContainer,{css:({ ["padding"] : "4", ["maxWidth"] : "1200px" }),size:"3"},jsx(RadixThemesFlex,{align:"start",className:"rx-Stack",css:({ ["width"] : "100%" }),direction:"column",gap:"4"},jsx(RadixThemesFlex,{align:"start",className:"rx-Stack",css:({ ["width"] : "100%", ["padding"] : "4" }),direction:"row",justify:"between",gap:"3"},jsx(RadixThemesHeading,{size:"6"},"Activity Stream"),jsx(RadixThemesBadge,{color:"blue",variant:"soft"},jsx(Bare_comp_bb22fc1d83241b3e13c8fc89df6ddd1b_f8ce5aac,{},)),jsx(Button_button_29078524021c1baca479c0783c1bd0f3_f8ce5aac,{},"Collapse all")),jsx(Fragment,{},jsx(Cond_comp_a3f9be73b2b103ae522a3ccdb282c286_f8ce5aac,{},jsx(Fragment,{},jsx(RadixThemesCallout.Root,{css:({ ["color"] : "red" })},jsx(Fragment,{},),jsx(RadixThemesCallout.Text,{},jsx(Bare_comp_14ca4209605d34b9d54e836a2beafeb9_f8ce5aac,{},)))),jsx(Fragment,{},))),jsx(RadixThemesSeparator,{size:"4"},),jsx(RadixThemesCard,{css:({ ["padding"] : "4", ["width"] : "100%" })},jsx(Fragment,{},jsx(Cond_comp_d069d81bb85a5c5843609e2b04d53a67_f8ce5aac,{},jsx(Fragment,{},jsx(Foreach_comp_0f3679e577e0540e5d12e33691beafb9_f8ce5aac,{},)),jsx(Fragment,{},jsx(RadixThemesText,{as:"p",color:"gray",size:"3"},"No events recorded"))))))),jsx("title",{},"Activity Stream"),jsx("meta",{content:"favicon.ico",property:"og:image"},))
  )
}
Component.displayName = "Component(activity)";

export default Component;
