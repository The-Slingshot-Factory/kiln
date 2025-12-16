#pragma once

#include <imgui.h>
#include <string>

// Base class for modal dialogs - reduces boilerplate
class Dialog
{
public:
    virtual ~Dialog() = default;
    
    // Open the dialog
    void open() { shouldOpen = true; }
    
    // Check if dialog is currently open
    bool isOpen() const { return isShowing; }
    
    // Render the dialog - call every frame
    // Returns true if action was completed (e.g. Create clicked)
    bool render()
    {
        if (shouldOpen)
        {
            ImGui::OpenPopup(getTitle());
            shouldOpen = false;
            isShowing = true;
            onOpen();
        }
        
        bool completed = false;
        
        ImVec2 center = ImGui::GetMainViewport()->GetCenter();
        ImGui::SetNextWindowPos(center, ImGuiCond_Appearing, ImVec2(0.5f, 0.5f));
        
        if (getWidth() > 0)
        {
            ImGui::SetNextWindowSize(ImVec2(getWidth(), 0), ImGuiCond_Appearing);
        }
        
        if (ImGui::BeginPopupModal(getTitle(), &isShowing, ImGuiWindowFlags_None))
        {
            renderContent();
            
            ImGui::Spacing();
            ImGui::Separator();
            ImGui::Spacing();
            
            // Centered buttons
            float buttonWidth = 100.0f;
            float buttonsWidth = buttonWidth * 2 + ImGui::GetStyle().ItemSpacing.x;
            ImGui::SetCursorPosX((ImGui::GetWindowWidth() - buttonsWidth) / 2.0f);
            
            if (ImGui::Button("Cancel", ImVec2(buttonWidth, 0)))
            {
                isShowing = false;
                ImGui::CloseCurrentPopup();
            }
            
            ImGui::SameLine();
            
            bool canConfirm = canComplete();
            if (!canConfirm) ImGui::BeginDisabled();
            
            if (ImGui::Button(getConfirmText(), ImVec2(buttonWidth, 0)))
            {
                onComplete();
                completed = true;
                isShowing = false;
                ImGui::CloseCurrentPopup();
            }
            
            if (!canConfirm) ImGui::EndDisabled();
            
            ImGui::EndPopup();
        }
        
        return completed;
    }

protected:
    // Override these in subclasses
    virtual const char* getTitle() const = 0;
    virtual const char* getConfirmText() const { return "Create"; }
    virtual float getWidth() const { return 320.0f; }
    virtual void onOpen() {}
    virtual void renderContent() = 0;
    virtual bool canComplete() const { return true; }
    virtual void onComplete() = 0;

private:
    bool shouldOpen = false;
    bool isShowing = false;
};

