
import {ReflexEvent,applyEventActions,isTrue} from "$/utils/state"
import {StateContexts,addEvents} from "$/utils/context"
import {Fragment,memo,useCallback,useContext,useEffect} from "react"
import {jsx} from "@emotion/react"
import {Badge as RadixThemesBadge,Button as RadixThemesButton,Flex as RadixThemesFlex,Text as RadixThemesText} from "@radix-ui/themes"








export const Bare_comp_bb22fc1d83241b3e13c8fc89df6ddd1b_f8ce5aac = memo(({children}) => {
    const reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state = useContext(StateContexts.reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state)



    return(
        reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state.activity_summary_rx_state_
    )
});
Bare_comp_bb22fc1d83241b3e13c8fc89df6ddd1b_f8ce5aac.displayName = "Bare";

export const Button_button_29078524021c1baca479c0783c1bd0f3_f8ce5aac = memo(({children}) => {
    const on_click_7a990df60fc44ef6396383465fa3f76d = useCallback(((_e) => (addEvents([(ReflexEvent("reflex___state____state.theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state.collapse_all", ({  }), ({  })))], [_e], ({  })))), [addEvents, ReflexEvent])



    return(
        jsx(RadixThemesButton,{onClick:on_click_7a990df60fc44ef6396383465fa3f76d,size:"1",variant:"ghost"},children)
    )
});
Button_button_29078524021c1baca479c0783c1bd0f3_f8ce5aac.displayName = "Button";

export const Bare_comp_14ca4209605d34b9d54e836a2beafeb9_f8ce5aac = memo(({children}) => {
    const reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state = useContext(StateContexts.reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state)



    return(
        reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state.error_rx_state_
    )
});
Bare_comp_14ca4209605d34b9d54e836a2beafeb9_f8ce5aac.displayName = "Bare";

export const Cond_comp_a3f9be73b2b103ae522a3ccdb282c286_f8ce5aac = memo(({children}) => {
    const reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state = useContext(StateContexts.reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state)



    return(
        (!((reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state.error_rx_state_?.valueOf?.() === ""?.valueOf?.()))?(children?.at?.(0)):(children?.at?.(1)))
    )
});
Cond_comp_a3f9be73b2b103ae522a3ccdb282c286_f8ce5aac.displayName = "Cond";

export const Foreach_comp_0f3679e577e0540e5d12e33691beafb9_f8ce5aac = memo(({children}) => {
    const reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state = useContext(StateContexts.reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state)



    return(
        Array.prototype.map.call(reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state.activity_view_rx_state_ ?? [],((row_rx_state_,index_9e7dc13d6c7fa41addd66a07442ae2d7)=>(jsx(RadixThemesFlex,{align:"start",className:"rx-Stack",css:({ ["width"] : "100%", ["paddingTop"] : "2", ["paddingBottom"] : "2" }),direction:"column",key:index_9e7dc13d6c7fa41addd66a07442ae2d7,gap:"1"},jsx(RadixThemesFlex,{align:"center",className:"rx-Stack",css:({ ["width"] : "100%" }),direction:"row",gap:"2"},jsx(RadixThemesBadge,{css:({ ["color"] : row_rx_state_?.["color"] }),radius:"full",size:"1",variant:"solid"},"ROW_RX_STATE_?.[\"SEVERITY\"]"),jsx(RadixThemesText,{as:"p",color:"gray",size:"1"},row_rx_state_?.["agent"]),jsx(RadixThemesText,{as:"p",color:"gray",size:"1"},row_rx_state_?.["timestamp"])),jsx(RadixThemesText,{as:"p",size:"2"},row_rx_state_?.["message"]),jsx(Fragment,{},(isTrue(row_rx_state_?.["has_details"])?(jsx(Fragment,{},jsx(RadixThemesFlex,{align:"start",className:"rx-Stack",css:({ ["width"] : "100%" }),direction:"column",gap:"1"},jsx(RadixThemesButton,{onClick:((_e) => (addEvents([(ReflexEvent("reflex___state____state.theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state.toggle_panel", ({ ["panel_id"] : row_rx_state_?.["panel_id"] }), ({  })))], [_e], ({  })))),size:"1",variant:"ghost"},(isTrue(row_rx_state_?.["is_open"]) ? "\u25bc" : "\u25b6")),jsx(RadixThemesText,{as:"p",size:"2",weight:"bold"},"Details"),jsx(RadixThemesText,{as:"p",color:"gray",size:"1"},row_rx_state_?.["detail_label"]),jsx(Fragment,{},(isTrue(row_rx_state_?.["is_open"])?(jsx(Fragment,{},jsx(RadixThemesText,{as:"p",color:"gray",css:({ ["whiteSpace"] : "pre-line" }),size:"1"},row_rx_state_?.["detail_text"]))):(jsx(Fragment,{},))))))):(jsx(Fragment,{},))))))))
    )
});
Foreach_comp_0f3679e577e0540e5d12e33691beafb9_f8ce5aac.displayName = "Foreach";

export const Cond_comp_d069d81bb85a5c5843609e2b04d53a67_f8ce5aac = memo(({children}) => {
    const reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state = useContext(StateContexts.reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state)



    return(
        ((reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state.activity_view_rx_state_.length > 0)?(children?.at?.(0)):(children?.at?.(1)))
    )
});
Cond_comp_d069d81bb85a5c5843609e2b04d53a67_f8ce5aac.displayName = "Cond";
