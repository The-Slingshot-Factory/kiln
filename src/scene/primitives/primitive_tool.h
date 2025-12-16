#pragma once

#include "../scene.h"

// Abstract base class for tools that create or modify scene primitives
class PrimitiveTool
{
public:
    virtual ~PrimitiveTool() = default;
    
    // The name to display in menus (e.g. "Plane...")
    virtual const char* getName() const = 0;
    
    // Called when the tool is activated (e.g. from a menu)
    virtual void onActivate(Scene* scene) = 0;
    
    // Called every frame to render UI (popups, etc.)
    // Returns the newly created node if successful, or nullptr otherwise
    virtual SceneNode* render() = 0;
};

