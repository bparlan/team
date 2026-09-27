
import {ReflexEvent,applyEventActions,isTrue} from "$/utils/state"
import {Badge as RadixThemesBadge,Button as RadixThemesButton,Container as RadixThemesContainer,Table as RadixThemesTable} from "@radix-ui/themes"
import {StateContexts,addEvents} from "$/utils/context"
import {Fragment,memo,useCallback,useContext,useEffect} from "react"
import {jsx} from "@emotion/react"








export const Button_button_e24623ba4255c629ae1cf3b08abac8a8_890f0220 = memo(({children}) => {
    const on_click_3ddcc551db4e980444bc171a134c93b3 = useCallback(((_e) => (addEvents([(ReflexEvent("reflex___state____state.theteam_dashboard___state____dashboard_state.load_all", ({  }), ({  })))], [_e], ({  })))), [addEvents, ReflexEvent])



    return(
        jsx(RadixThemesButton,{color:"blue",onClick:on_click_3ddcc551db4e980444bc171a134c93b3},children)
    )
});
Button_button_e24623ba4255c629ae1cf3b08abac8a8_890f0220.displayName = "Button";

export const Foreach_comp_642f51fc4f791ed369e871ebfbdcc38b_890f0220 = memo(({children}) => {
    const reflex___state____state__theteam_dashboard___state____dashboard_state = useContext(StateContexts.reflex___state____state__theteam_dashboard___state____dashboard_state)



    return(
        Array.prototype.map.call(reflex___state____state__theteam_dashboard___state____dashboard_state.scheduled_tasks_list_rx_state_ ?? [],((s_rx_state_,index_b8504cec686ac65b4645610e9830b682)=>(jsx(RadixThemesTable.Row,{key:index_b8504cec686ac65b4645610e9830b682},jsx(RadixThemesTable.Cell,{},s_rx_state_?.["id"]),jsx(RadixThemesTable.Cell,{},s_rx_state_?.["interval"]),jsx(RadixThemesTable.Cell,{},s_rx_state_?.["next_run"])))))
    )
});
Foreach_comp_642f51fc4f791ed369e871ebfbdcc38b_890f0220.displayName = "Foreach";

export const Cond_comp_ec3dc2bd15657244c860bf48aa0053c7_890f0220 = memo(({children}) => {
    const reflex___state____state__theteam_dashboard___state____dashboard_state = useContext(StateContexts.reflex___state____state__theteam_dashboard___state____dashboard_state)



    return(
        ((reflex___state____state__theteam_dashboard___state____dashboard_state.scheduled_count_rx_state_ > 0)?(children?.at?.(0)):(children?.at?.(1)))
    )
});
Cond_comp_ec3dc2bd15657244c860bf48aa0053c7_890f0220.displayName = "Cond";

export const Bare_comp_c526c83af419243066512b4e1264df8f_890f0220 = memo(({children}) => {
    const reflex___state____state__theteam_dashboard___state____dashboard_state = useContext(StateContexts.reflex___state____state__theteam_dashboard___state____dashboard_state)



    return(
        reflex___state____state__theteam_dashboard___state____dashboard_state.daemon_running_text_rx_state_
    )
});
Bare_comp_c526c83af419243066512b4e1264df8f_890f0220.displayName = "Bare";

export const Badge_badge_138208de3c56e0bf7ea967ec9dd62aea_890f0220 = memo(({children}) => {
    const reflex___state____state__theteam_dashboard___state____dashboard_state = useContext(StateContexts.reflex___state____state__theteam_dashboard___state____dashboard_state)



    return(
        jsx(RadixThemesBadge,{color:((reflex___state____state__theteam_dashboard___state____dashboard_state.daemon_running_text_rx_state_?.valueOf?.() === "Running"?.valueOf?.()) ? "green" : "red"),variant:"solid"},children)
    )
});
Badge_badge_138208de3c56e0bf7ea967ec9dd62aea_890f0220.displayName = "Badge";

export const Bare_comp_c87a43ab58f6bef27a66000b36cdaca6_890f0220 = memo(({children}) => {
    const reflex___state____state__theteam_dashboard___state____dashboard_state = useContext(StateContexts.reflex___state____state__theteam_dashboard___state____dashboard_state)



    return(
        ("Started: "+(isTrue(reflex___state____state__theteam_dashboard___state____dashboard_state.daemon_display_rx_state_?.["started"]) ? reflex___state____state__theteam_dashboard___state____dashboard_state.daemon_display_rx_state_?.["started"] : ""))
    )
});
Bare_comp_c87a43ab58f6bef27a66000b36cdaca6_890f0220.displayName = "Bare";

export const Bare_comp_c5f5eccbf55e9168e629bd271863a762_890f0220 = memo(({children}) => {
    const reflex___state____state__theteam_dashboard___state____dashboard_state = useContext(StateContexts.reflex___state____state__theteam_dashboard___state____dashboard_state)



    return(
        ("Tasks executed: "+(isTrue(reflex___state____state__theteam_dashboard___state____dashboard_state.daemon_display_rx_state_?.["executed"]) ? reflex___state____state__theteam_dashboard___state____dashboard_state.daemon_display_rx_state_?.["executed"] : 0))
    )
});
Bare_comp_c5f5eccbf55e9168e629bd271863a762_890f0220.displayName = "Bare";

export const Bare_comp_f2e79dd604d294f927721a9f529ea19a_890f0220 = memo(({children}) => {
    const reflex___state____state__theteam_dashboard___state____dashboard_state = useContext(StateContexts.reflex___state____state__theteam_dashboard___state____dashboard_state)



    return(
        ("Last check: "+reflex___state____state__theteam_dashboard___state____dashboard_state.daemon_last_check_text_rx_state_)
    )
});
Bare_comp_f2e79dd604d294f927721a9f529ea19a_890f0220.displayName = "Bare";

export const Cond_comp_86c543f52c38cd3198fb6db46172a00c_890f0220 = memo(({children}) => {
    const reflex___state____state__theteam_dashboard___state____dashboard_state = useContext(StateContexts.reflex___state____state__theteam_dashboard___state____dashboard_state)



    return(
        ((reflex___state____state__theteam_dashboard___state____dashboard_state.daemon_running_text_rx_state_?.valueOf?.() === "Running"?.valueOf?.())?(children?.at?.(0)):(children?.at?.(1)))
    )
});
Cond_comp_86c543f52c38cd3198fb6db46172a00c_890f0220.displayName = "Cond";

export const Foreach_comp_eda8b980ce787cd763c4b58767de9222_890f0220 = memo(({children}) => {
    const reflex___state____state__theteam_dashboard___state____dashboard_state = useContext(StateContexts.reflex___state____state__theteam_dashboard___state____dashboard_state)



    return(
        Array.prototype.map.call(reflex___state____state__theteam_dashboard___state____dashboard_state.tasks_rx_state_ ?? [],((t_rx_state_,index_9e7dc13d6c7fa41addd66a07442ae2d7)=>(jsx(RadixThemesTable.Row,{key:index_9e7dc13d6c7fa41addd66a07442ae2d7},jsx(RadixThemesTable.Cell,{},t_rx_state_?.["id"]),jsx(RadixThemesTable.Cell,{},t_rx_state_?.["name"]),jsx(RadixThemesTable.Cell,{},jsx(RadixThemesBadge,{color:"gray",variant:"soft"},t_rx_state_?.["type"])),jsx(RadixThemesTable.Cell,{},t_rx_state_?.["priority"]),jsx(RadixThemesTable.Cell,{},jsx(RadixThemesBadge,{color:"gray"},t_rx_state_?.["schedule_text"]))))))
    )
});
Foreach_comp_eda8b980ce787cd763c4b58767de9222_890f0220.displayName = "Foreach";

export const Cond_comp_75d8039380d4ce8d0b67edca458673f5_890f0220 = memo(({children}) => {
    const reflex___state____state__theteam_dashboard___state____dashboard_state = useContext(StateContexts.reflex___state____state__theteam_dashboard___state____dashboard_state)



    return(
        ((reflex___state____state__theteam_dashboard___state____dashboard_state.task_count_rx_state_ > 0)?(children?.at?.(0)):(children?.at?.(1)))
    )
});
Cond_comp_75d8039380d4ce8d0b67edca458673f5_890f0220.displayName = "Cond";

export const Container_container_a053053593036a0493517480ad7782c5_890f0220 = memo(({children}) => {
    
                useEffect(() => {
                    ((...args) => (addEvents([(ReflexEvent("reflex___state____state.theteam_dashboard___state____dashboard_state.load_all", ({  }), ({  })))], args, ({  }))))()
                    return () => {
                        
                    }
                }, []);



    return(
        jsx(RadixThemesContainer,{css:({ ["padding"] : "4", ["maxWidth"] : "1200px" }),size:"3"},children)
    )
});
Container_container_a053053593036a0493517480ad7782c5_890f0220.displayName = "Container";
