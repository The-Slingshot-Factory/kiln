#pragma once

#include "dialog.h"
#include <filesystem>
#include <cstring>

class NewFolderDialog : public Dialog
{
public:
    void setParentPath(const std::filesystem::path& path)
    {
        parentPath = path;
    }
    
    std::filesystem::path getCreatedPath() const { return createdPath; }

protected:
    const char* getTitle() const override { return "New Folder"; }
    float getWidth() const override { return 350.0f; }
    
    void onOpen() override
    {
        std::memset(folderName, 0, sizeof(folderName));
        createdPath.clear();
    }
    
    void renderContent() override
    {
        ImGui::Text("Create new folder in:");
        ImGui::TextColored(ImVec4(0.7f, 0.7f, 0.7f, 1.0f), "%s", parentPath.string().c_str());
        ImGui::Spacing();
        
        ImGui::Text("Folder name:");
        ImGui::SetNextItemWidth(-1);
        ImGui::InputText("##FolderName", folderName, sizeof(folderName));
        
        if (ImGui::IsWindowAppearing())
        {
            ImGui::SetKeyboardFocusHere(-1);
        }
    }
    
    bool canComplete() const override
    {
        return std::strlen(folderName) > 0;
    }
    
    void onComplete() override
    {
        std::filesystem::path newPath = parentPath / folderName;
        try
        {
            if (std::filesystem::create_directory(newPath))
            {
                createdPath = newPath;
            }
        }
        catch (const std::filesystem::filesystem_error&)
        {
        }
    }

private:
    std::filesystem::path parentPath;
    std::filesystem::path createdPath;
    char folderName[256] = "";
};

